'''

 V-Ray/Blender 2.5

 http://vray.cgdo.ru

 Author: Andrey M. Izrantsev (aka bdancer)
 E-Mail: izrantsev@gmail.com

 This plugin is protected by the GNU General Public License v.2

 This program is free software: you can redioutibute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is dioutibuted in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.

 All Rights Reserved. V-Ray(R) is a registered trademark of Chaos Software.

'''


''' Python modules  '''
import math
import os
import string
import subprocess
import sys
import tempfile
import time

''' Blender modules '''
import bpy
import mathutils

''' vb modules '''
from vb25.utils import *
from vb25.shaders import *
from vb25.plugin_manager import *

''' vb dev modules '''
try:
	from vb25.nodes_material import *
except:
	pass


VERSION= '2.5.10'

mesh_lights= []

'''
  MESHES
'''
def write_mesh_hq(ofile, sce, ob):
	timer= time.clock()

	sys.stdout.write("V-Ray/Blender: Generating HQ file (Frame: %i; File: %s)..." % (sce.frame_current,ofile.name))
	sys.stdout.flush()

	GeomMeshFile= ob.data.vray.GeomMeshFile

	me=  ob.create_mesh(sce, True, 'RENDER')
	dme= None

	if GeomMeshFile.animation and GeomMeshFile.add_velocity:
		if sce.frame_current != sce.frame_end:
			sce.frame_set(sce.frame_current+1)
			dme= ob.create_mesh(sce, True, 'RENDER')

	if GeomMeshFile.apply_transforms:
		me.transform(ob.matrix_world)
		if dme:
			dme.transform(ob.matrix_world)

	if dme:
		for v,dv in zip(me.vertices,dme.vertices):
			ofile.write("v=%.6f,%.6f,%.6f\n" % tuple(v.co))
			ofile.write("l=%.6f,%.6f,%.6f\n" % tuple([dc-c for c,dc in zip(v.co,dv.co)]))
	else:
		for vertex in me.vertices:
			ofile.write("v=%.6f,%.6f,%.6f\n" % tuple(vertex.co))
			ofile.write("l=0.0,0.0,0.0\n")

	k= 0
	for face in me.faces:
		vert_order= (0,1,2,2,3,0)
		if len(face.vertices) == 4:
			ofile.write("f=%d,%d,%d;%d\n" % (face.vertices[0], face.vertices[1], face.vertices[2], face.material_index + 1))
			ofile.write("f=%d,%d,%d;%d\n" % (face.vertices[2], face.vertices[3], face.vertices[0], face.material_index + 1))
			ofile.write("fn=%i,%i,%i\n" % (k,k+1,k+2))
			ofile.write("fn=%i,%i,%i\n" % (k+3,k+4,k+5))
			k+= 6
		else:
			vert_order= (0,1,2)
			ofile.write("f=%d,%d,%d;%d\n" % (face.vertices[0], face.vertices[1], face.vertices[2], face.material_index + 1))
			ofile.write("fn=%i,%i,%i\n" % (k,k+1,k+2))
			k+= 3
		for v in vert_order:
			if face.use_smooth:
				ofile.write("n=%.6f,%.6f,%.6f\n" % tuple(me.vertices[face.vertices[v]].normal))
			else:
				ofile.write("n=%.6f,%.6f,%.6f\n" % tuple(face.normal))
	if len(me.uv_textures):
		uv_layer= me.uv_textures[0]
		k= 0
		for face in uv_layer.data:
			for i in range(len(face.uv)):
				ofile.write("uv=%.6f,%.6f,0.0\n" % (face.uv[i][0], face.uv[i][1]))
			if len(face.uv) == 4:
				ofile.write("uf=%i,%i,%i\n" % (k,k+1,k+2))
				ofile.write("uf=%i,%i,%i\n" % (k+2,k+3,k))
				k+= 4
			else:
				ofile.write("uf=%i,%i,%i\n" % (k,k+1,k+2))
				k+= 3
	ofile.write("\n")
	
	sys.stdout.write(" done [%.2f]\n" % (time.clock() - timer))
	sys.stdout.flush()


def generate_proxy(sce, ob, vrmesh, append=False):
	hq_file= tempfile.NamedTemporaryFile(mode='w', suffix=".hq", delete=False)
	write_mesh_hq(hq_file, sce, ob)
	hq_file.close()
	proxy_creator(hq_file.name, vrmesh, append)
	os.remove(hq_file.name)


def write_geometry_python(sce, geometry_file):
	sys.stdout.write("V-Ray/Blender: Exporting meshes...\n")

	VRayScene= sce.vray
	VRayExporter= VRayScene.exporter

	uv_layers= get_uv_layers(sce)

	exported_meshes= []

	def write_mesh(exported_meshes, ob):
		me= ob.create_mesh(sce, True, 'RENDER')

		me_name= get_name(ob.data, "ME")

		if VRayExporter.use_instances:
			if me_name in exported_meshes:
				return
			exported_meshes.append(me_name)
		else:
			me_name= get_name(ob, "ME")

		if VRayExporter.debug:
			print("V-Ray/Blender: [%i]\n  Object: %s\n    Mesh: %s"
				  %(sce.frame_current,
					ob.name,
					ob.data.name))
		else:
			if PLATFORM == "linux2":
				sys.stdout.write("V-Ray/Blender: [%i] Mesh: \033[0;32m%s\033[0m                              \r"
								 %(sce.frame_current, ob.data.name))
			else:
				sys.stdout.write("V-Ray/Blender: [%i] Mesh: %s                              \r"
								 %(sce.frame_current, ob.data.name))
			sys.stdout.flush()

		ofile.write("\nGeomStaticMesh %s {"%(me_name))

		ofile.write("\n\tvertices= interpolate((%d, ListVector("%(sce.frame_current))
		for v in me.vertices:
			if(v.index):
				ofile.write(",")
			ofile.write("Vector(%.6f,%.6f,%.6f)"%(tuple(v.co)))
		ofile.write(")));")

		ofile.write("\n\tfaces= interpolate((%d, ListInt("%(sce.frame_current))
		for f in me.faces:
			if f.index:
				ofile.write(",")
			if len(f.vertices) == 4:
				ofile.write("%d,%d,%d,%d,%d,%d"%(
					f.vertices[0], f.vertices[1], f.vertices[2],
					f.vertices[2], f.vertices[3], f.vertices[0]))
			else:
				ofile.write("%d,%d,%d"%(
					f.vertices[0], f.vertices[1], f.vertices[2]))
		ofile.write(")));")

		ofile.write("\n\tface_mtlIDs= ListInt(")
		for f in me.faces:
			if f.index:
				ofile.write(",")
			if len(f.vertices) == 4:
				ofile.write("%d,%d"%(
					f.material_index + 1, f.material_index + 1))
			else:
				ofile.write("%d"%(
					f.material_index + 1))
		ofile.write(");")

		ofile.write("\n\tnormals= interpolate((%d, ListVector("%(sce.frame_current))
		for f in me.faces:
			if f.index:
				ofile.write(",")

			if len(f.vertices) == 4:
				vertices= (0,1,2,2,3,0)
			else:
				vertices= (0,1,2)

			comma= 0
			for v in vertices:
				if comma:
					ofile.write(",")
				comma= 1

				if f.use_smooth:
					ofile.write("Vector(%.6f,%.6f,%.6f)"%(
						tuple(me.vertices[f.vertices[v]].normal)
					))
				else:
					ofile.write("Vector(%.6f,%.6f,%.6f)"%(
						tuple(f.normal)
					))
		ofile.write(")));")

		ofile.write("\n\tfaceNormals= ListInt(")
		k= 0
		for f in me.faces:
			if f.index:
				ofile.write(",")

			if len(f.vertices) == 4:
				vertices= 6
			else:
				vertices= 3

			for v in range(vertices):
				if v:
					ofile.write(",")
				ofile.write("%d"%(k))
				k+= 1
		ofile.write(");")

		if len(me.uv_textures):
			ofile.write("\n\tmap_channels= List(")

			for uv_texture_idx,uv_texture in enumerate(me.uv_textures):
				if uv_texture_idx:
					ofile.write(",")

				uv_layer_index= get_uv_layer_id(sce, uv_layers, uv_texture.name)

				ofile.write("\n\t\t// %s"%(uv_texture.name))
				ofile.write("\n\t\tList(%d,ListVector("%(uv_layer_index))

				for f in range(len(uv_texture.data)):
					if f:
						ofile.write(",")

					face= uv_texture.data[f]

					for i in range(len(face.uv)):
						if i:
							ofile.write(",")
						ofile.write("Vector(%.6f,%.6f,0.0)"%(
							face.uv[i][0],
							face.uv[i][1]
						))

				ofile.write("),ListInt(")

				k= 0
				for f in range(len(uv_texture.data)):
					if f:
						ofile.write(",")

					face= uv_texture.data[f]

					if len(face.uv) == 4:
						ofile.write("%i,%i,%i,%i,%i,%i" % (k,k+1,k+2,k+2,k+3,k))
						k+= 4
					else:
						ofile.write("%i,%i,%i" % (k,k+1,k+2))
						k+= 3
				ofile.write("))")

			ofile.write(");")
		ofile.write("\n}\n")

	for t in range(sce.render.threads):
		ofile= open(geometry_file[:-11]+"_%.2i.vrscene"%(t), 'w')
		ofile.close()

	ofile= open(geometry_file, 'w')
	ofile.write("// V-Ray/Blender %s\n"%(VERSION))
	ofile.write("// Geometry file\n")

	timer= time.clock()

	OBJECTS= []
	
	for ob in sce.objects:
		if ob.type in ('LAMP','CAMERA','ARMATURE','EMPTY','LATTICE'):
			continue
		if ob.data.vray.GeomMeshFile.use:
			continue
		if VRayExporter.mesh_active_layers:
			if not object_on_visible_layers(sce,ob):
				continue

		OBJECTS.append(ob)

	if VRayExporter.animation:
		cur_frame= sce.frame_current
		sce.frame_set(sce.frame_start)
		f= sce.frame_start
		while(f <= sce.frame_end):
			exported_meshes= []
			sce.frame_set(f)
			for ob in OBJECTS:
				write_mesh(exported_meshes,ob)
			f+= sce.frame_step
		sce.frame_set(cur_frame)
	else:
		for ob in OBJECTS:
			write_mesh(exported_meshes,ob)

	ofile.close()
	print("V-Ray/Blender: Exporting meshes... done [%s]                    "%(time.clock() - timer))


def write_geometry(sce):
	VRayScene= sce.vray
	VRayExporter= VRayScene.exporter

	geometry_file= get_filenames(sce,'geometry')

	try:
		bpy.ops.vray.export_meshes(
			filepath= geometry_file[:-11],
			use_active_layers= VRayExporter.mesh_active_layers,
			use_animation= VRayExporter.animation,
			use_instances= VRayExporter.use_instances,
			check_animated= VRayExporter.check_animated,
		)
	except:
		write_geometry_python(sce, geometry_file)


def write_GeomMayaHair(ofile, ob, ps, name):
	num_hair_vertices= []
	hair_vertices=     []
	widths=            []

	for p,particle in enumerate(ps.particles):
		sys.stdout.write("V-Ray/Blender: Object: %s => Hair: %i\r" % (ob.name, p))
		sys.stdout.flush()
		num_hair_vertices.append(str(len(particle.hair)))
		for segment in particle.hair:
			hair_vertices.append("Vector(%.6f,%.6f,%.6f)" % tuple(segment.co))
			widths.append(str(0.01)) # TODO

	ofile.write("\nGeomMayaHair %s {"%(name))
	ofile.write("\n\tnum_hair_vertices= interpolate((%d,ListInt(%s)));"%(sce.frame_current, ','.join(num_hair_vertices)))
	ofile.write("\n\thair_vertices= interpolate((%d,ListVector(%s)));"%(sce.frame_current,  ','.join(hair_vertices)))
	ofile.write("\n\twidths= interpolate((%d,ListFloat(%s)));"%(sce.frame_current,          ','.join(widths)))
	ofile.write("\n}\n")


def write_mesh_displace(ofile, mesh, params):
	slot= params.get('slot')
	ob=   params.get('object')

	plugin= 'GeomDisplacedMesh'
	name= "%s_%s" % (plugin, mesh)

	VRaySlot= slot.texture.vray_slot
	GeomDisplacedMesh= VRaySlot.GeomDisplacedMesh
	displacement_amount= GeomDisplacedMesh.displacement_amount

	if ob:
		name= "%s_%s" % (plugin, clean_string(ob.name))
		if ob.vray.GeomDisplacedMesh.use:
			GeomDisplacedMesh= ob.vray.GeomDisplacedMesh
	
	ofile.write("\n%s %s {"%(plugin,name))
	ofile.write("\n\tmesh= %s;" % mesh)
	ofile.write("\n\tdisplacement_tex_color= %s;" % params['texture'])
	if GeomDisplacedMesh.type == '2D':
		ofile.write("\n\tdisplace_2d= 1;")
	elif GeomDisplacedMesh.type == '3D':
		ofile.write("\n\tvector_displacement= 1;")
	else:
		ofile.write("\n\tdisplace_2d= 0;")
		ofile.write("\n\tvector_displacement= 0;")
	for param in OBJECT_PARAMS[plugin]:
		if param == 'displacement_amount':
			if ob and ob.vray.GeomDisplacedMesh.use:
				if GeomDisplacedMesh.amount_type == 'OVER':
					value= GeomDisplacedMesh.displacement_amount
				else:
					value= GeomDisplacedMesh.amount_mult * displacement_amount
			else:
				value= displacement_amount
		else:
			value= getattr(GeomDisplacedMesh,param)
		ofile.write("\n\t%s= %s;"%(param,a(sce,value)))
	ofile.write("\n}\n")

	return name


def write_mesh_file(ofile, exported_proxy, ob):
	proxy= ob.data.vray.GeomMeshFile
	proxy_name= "Proxy_%s" % clean_string(os.path.basename(os.path.normpath(bpy.path.abspath(proxy.file)))[:-7])

	if proxy_name not in exported_proxy:
		exported_proxy.append(proxy_name)
		
		ofile.write("\nGeomMeshFile %s {" % proxy_name)
		ofile.write("\n\tfile= \"%s\";" % get_full_filepath(sce,ob,proxy.file))
		ofile.write("\n\tanim_speed= %i;" % proxy.anim_speed)
		ofile.write("\n\tanim_type= %i;" % PROXY_ANIM_TYPE[proxy.anim_type])
		ofile.write("\n\tanim_offset= %i;" % (proxy.anim_offset - 1))
		ofile.write("\n}\n")

	return proxy_name



'''
  MATERIALS
'''
def lamp_defaults(la):
	VRayLamp= la.vray

	return {
		'color':       (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(la.color)),                 0, 'NONE'),
		'intensity':   (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple([VRayLamp.intensity]*3)),   0, 'NONE'),
		'shadowColor': (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(VRayLamp.shadowColor)),     0, 'NONE'),
	}

def material_defaults(ma):
	VRayMaterial=    ma.vray
	BRDFVRayMtl=     VRayMaterial.BRDFVRayMtl
	BRDFSSS2Complex= VRayMaterial.BRDFSSS2Complex
	EnvironmentFog=  VRayMaterial.EnvironmentFog

	if VRayMaterial.type == 'MTL':
		return {
			'diffuse':   (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(ma.diffuse_color)),          0, 'NONE'),
			'roughness': (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple([BRDFVRayMtl.roughness]*3)), 0, 'NONE'),
			'opacity':   (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple([ma.alpha]*3)),              0, 'NONE'),

			'reflect_glossiness':  (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple([BRDFVRayMtl.reflect_glossiness]*3)), 0, 'NONE'),
			'hilight_glossiness':  (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple([BRDFVRayMtl.hilight_glossiness]*3)), 0, 'NONE'),
		
			'reflect':             (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(BRDFVRayMtl.reflect_color)),           0, 'NONE'),
			'anisotropy':          (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple([BRDFVRayMtl.anisotropy]*3)),          0, 'NONE'),
			'anisotropy_rotation': (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple([BRDFVRayMtl.anisotropy_rotation]*3)), 0, 'NONE'),
			'refract':             (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(BRDFVRayMtl.refract_color)),           0, 'NONE'),
			'refract_glossiness':  (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple([BRDFVRayMtl.refract_glossiness]*3)),  0, 'NONE'),
			'translucency_color':  (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(BRDFVRayMtl.translucency_color)),      0, 'NONE'),

			'fresnel_ior':  ("AColor(0.0,0.0,0.0,1.0)", 0, 'NONE'),
			'refract_ior':  ("AColor(0.0,0.0,0.0,1.0)", 0, 'NONE'),
			'normal':       ("AColor(0.0,0.0,0.0,1.0)", 0, 'NONE'),
			'displacement': ("AColor(0.0,0.0,0.0,1.0)", 0, 'NONE'),
		}

	elif VRayMaterial.type == 'EMIT':
		return {
			'diffuse':   (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(ma.diffuse_color)),          0, 'NONE'),
			'opacity':   (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple([ma.alpha]*3)),              0, 'NONE'),
		}
	
	elif VRayMaterial.type == 'SSS':
		return {
			'overall_color':       (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(ma.diffuse_color)),                   0, 'NONE'),
			'sub_surface_color':   (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(BRDFSSS2Complex.sub_surface_color)),  0, 'NONE'),
			'scatter_radius':      (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(BRDFSSS2Complex.scatter_radius)),     0, 'NONE'),
			'diffuse_color':       (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(BRDFSSS2Complex.diffuse_color)),      0, 'NONE'),
			'diffuse_amount':      (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple([BRDFSSS2Complex.diffuse_amount]*3)), 0, 'NONE'),
			'specular_color':      (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(BRDFSSS2Complex.specular_color)),     0, 'NONE'),
			'specular_amount':     ("AColor(0.0,0.0,0.0,1.0)", 0, 'NONE'),
			'specular_glossiness': ("AColor(0.0,0.0,0.0,1.0)", 0, 'NONE'),
		}
		
	elif VRayMaterial.type == 'VOL':
		return {
			'color_tex':    (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(ma.diffuse_color)),           0, 'NONE'),
			'emission_tex': (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(EnvironmentFog.emission)),    0, 'NONE'),
			'density_tex':  (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple([EnvironmentFog.density]*3)), 0, 'NONE'),
		}
	else:
		return {
			'diffuse':   (a(sce,"AColor(%.6f,%.6f,%.6f,1.0)"%tuple(ma.diffuse_color)),          0, 'NONE'),
		}

def write_lamp_textures(ofile, params):
	la= params['lamp']
	
	defaults= lamp_defaults(la)

	mapped_params= {
		'mapto': {},
	}
	
	for slot in la.texture_slots:
		if slot and slot.texture and slot.texture.type in TEX_TYPES:
			VRaySlot= slot.texture.vray_slot
			VRayLight= VRaySlot.VRayLight
			
			for key in defaults:
				use_slot= False
				factor=   1.0
				
				if getattr(VRayLight, 'map_'+key):
					use_slot= True
					factor=   getattr(VRayLight, key+'_mult')

				if use_slot:
					if key not in mapped_params['mapto']: # First texture
						mapped_params['mapto'][key]= []
						if factor < 1.0 or VRaySlot.blend_mode != 'NONE' or slot.use_stencil:
							mapped_params['mapto'][key].append(defaults[key])
					params['mapto']=    key
					params['slot']=     slot
					params['texture']=  slot.texture
					params['factor']=   factor
					mapped_params['mapto'][key].append((write_texture_factor(ofile, sce, params),
														slot.use_stencil,
														VRaySlot.blend_mode))
	if len(mapped_params['mapto']):
		debug(sce, "V-Ray/Blender: Lamp \"%s\" texture stack: %s" % (la.name,mapped_params['mapto']))
	
	for key in mapped_params['mapto']:
		if len(mapped_params['mapto'][key]):
			mapped_params['mapto'][key]= write_TexOutput(
				ofile,
				stack_write_shaders(ofile, stack_collapse_layers(mapped_params['mapto'][key])),
				{}
			)

	return mapped_params


def write_material_textures(ofile, params):
	ma= params['material']

	BRDFVRayMtl=     ma.vray.BRDFVRayMtl
	BRDFSSS2Complex= ma.vray.BRDFSSS2Complex
	EnvironmentFog=  ma.vray.EnvironmentFog

	defaults= material_defaults(ma)

	mapped_params= {
		'mapto': {},
		'values': {
			'normal_slot':       None,
			'displacement_slot': None,
		}
	}

	for i,slot in enumerate(ma.texture_slots):
		if ma.use_textures[i] and slot and slot.texture and slot.texture.type in TEX_TYPES:
			VRaySlot= slot.texture.vray_slot
			for key in defaults:
				factor= 1.0
				use_slot= False
				if key == 'diffuse':
					if slot.use_map_color_diffuse:
						use_slot= True
						factor= slot.diffuse_color_factor
				elif key == 'overall_color' and ma.vray.type == 'SSS':
					if slot.use_map_color_diffuse:
						use_slot= True
						factor= slot.diffuse_color_factor
				elif key == 'reflect':
					if slot.use_map_raymir:
						use_slot= True
						factor= slot.raymir_factor
				elif key == 'opacity':
					if slot.use_map_alpha:
						use_slot= True
						factor= slot.alpha_factor
				elif key == 'normal':
					if slot.use_map_normal:
						use_slot= True
						factor= VRaySlot.normal_mult
						mapped_params['values']['normal_slot']= slot
				else:
					if getattr(VRaySlot, 'map_'+key):
						use_slot= True
						factor= getattr(VRaySlot, key+'_mult')
						if key == 'displacement':
							mapped_params['values']['displacement_slot']= slot

				if use_slot:
					if key not in mapped_params['mapto']: # First texture
						mapped_params['mapto'][key]= []
						if factor < 1.0 or VRaySlot.blend_mode != 'NONE' or slot.use_stencil:
							mapped_params['mapto'][key].append(defaults[key])
					params['mapto']=    key
					params['slot']=     slot
					params['texture']=  slot.texture
					params['factor']=   factor
					mapped_params['mapto'][key].append(
						(write_texture_factor(ofile, sce, params), slot.use_stencil, VRaySlot.blend_mode)
					)

	if len(mapped_params['mapto']):
		debug(sce, "V-Ray/Blender: Material \"%s\" texture stack: %s" % (ma.name,mapped_params['mapto']))
	
	for key in mapped_params['mapto']:
		if len(mapped_params['mapto'][key]):
			mapped_params['mapto'][key]= write_TexOutput(
				ofile,
				stack_write_shaders(ofile, stack_collapse_layers(mapped_params['mapto'][key])),
				{} # TODO: TexOutput params
			)

	return mapped_params


def write_BRDFVRayMtl(ofile, ma, ma_name, mapped_params):
	defaults= material_defaults(ma)

	textures= mapped_params['mapto']
	values=   mapped_params['values']

	BRDFVRayMtl= ma.vray.BRDFVRayMtl

	brdf_name= "BRDFVRayMtl_%s"%(ma_name)

	ofile.write("\nBRDFVRayMtl %s {"%(brdf_name))
	ofile.write("\n\tbrdf_type= %s;"%(a(sce,BRDF_TYPE[BRDFVRayMtl.brdf_type])))

	for key in ('diffuse','reflect','refract','translucency_color'):
		ofile.write("\n\t%s= %s;" % (key, a(sce,textures[key]) if key in textures else defaults[key][0]))

	for key in ('roughness','reflect_glossiness','hilight_glossiness','fresnel_ior','refract_ior','anisotropy','anisotropy_rotation'):
		ofile.write("\n\t%s= %s;" % (key, "%s::out_intensity" % textures[key] if key in textures else a(sce,getattr(BRDFVRayMtl,key))))

	if 'opacity' in textures:
		ofile.write("\n\topacity= %s::out_intensity;" % textures['opacity'])
	else:
		ofile.write("\n\topacity= %s;" % a(sce,ma.alpha))

	for param in OBJECT_PARAMS['BRDFVRayMtl']:
		if param == 'translucency':
			value= TRANSLUCENSY[BRDFVRayMtl.translucency]
		elif param == 'anisotropy_rotation':
			value= BRDFVRayMtl.anisotropy_rotation / 360.0
		elif param == 'translucency_thickness':
			value= BRDFVRayMtl.translucency_thickness * 1000000000000
		elif param == 'option_glossy_rays_as_gi':
			value= GLOSSY_RAYS[BRDFVRayMtl.option_glossy_rays_as_gi]
		elif param == 'option_energy_mode':
			value= ENERGY_MODE[BRDFVRayMtl.option_energy_mode]
		else:
			value= getattr(BRDFVRayMtl,param)
		ofile.write("\n\t%s= %s;"%(param, a(sce,value)))
	ofile.write("\n}\n")

	return brdf_name


def write_BRDFBump(ofile, base_brdf, textures):
	brdf_name= "BRDFBump_%s"%(base_brdf)

	MAP_TYPE= {
		'EXPLICIT': 6,
		'WORLD':    4,
		'CAMERA':   3,
		'OBJECT':   2,
		'TANGENT':  1,
		'BUMP'   :  0
	}

	slot= textures['values']['normal_slot']
	VRaySlot= slot.texture.vray_slot
	BRDFBump= VRaySlot.BRDFBump

	ofile.write("\nBRDFBump %s {"%(brdf_name))
	ofile.write("\n\tbase_brdf= %s;" % base_brdf)
	ofile.write("\n\tmap_type= %d;" % MAP_TYPE[BRDFBump.map_type])
	ofile.write("\n\tbump_tex_color= %s;" % textures['mapto']['normal'])
	ofile.write("\n\tbump_tex_float= %s;" % textures['mapto']['normal'])
	ofile.write("\n\tbump_tex_mult= %s;" % a(sce,BRDFBump.bump_tex_mult))
	ofile.write("\n\tnormal_uvwgen= %s;" % VRaySlot.uvwgen)
	ofile.write("\n\tbump_shadows= %d;" % BRDFBump.bump_shadows)
	ofile.write("\n\tcompute_bump_for_shadows= %d;" % BRDFBump.compute_bump_for_shadows)
	ofile.write("\n}\n")

	return brdf_name


def write_BRDFSSS2Complex(ofile, ma, ma_name, textures):
	SINGLE_SCATTER= {
		'NONE':   0,
		'SIMPLE': 1,
		'SOLID':  2,
		'REFR':   3
	}

	BRDFSSS2Complex= ma.vray.BRDFSSS2Complex

	brdf_name= "BRDFSSS2Complex_%s"%(ma_name)

	ofile.write("\nBRDFSSS2Complex %s {" % brdf_name)

	for key in ('overall_color','diffuse_color','sub_surface_color','scatter_radius','specular_color'):
		ofile.write("\n\t%s= %s;" % (key, a(sce,textures[key]) if key in textures else a(sce,getattr(BRDFSSS2Complex,key))))

	for key in ('specular_amount','specular_glossiness','diffuse_amount'):
		ofile.write("\n\t%s= %s;" % (key, "%s::out_intensity" % textures[key] if key in textures else a(sce,getattr(BRDFSSS2Complex,key))))

	for param in OBJECT_PARAMS['BRDFSSS2Complex']:
		if param == 'single_scatter':
			value= SINGLE_SCATTER[BRDFSSS2Complex.single_scatter]
		else:
			value= getattr(BRDFSSS2Complex,param)
		ofile.write("\n\t%s= %s;"%(param, a(sce,value)))

	ofile.write("\n}\n")

	return brdf_name


def	write_material(ma, filters, object_params, ofile, name= None, ob= None, params= None):
	ma_name= name if name else get_name(ma,"Material")

	VRayMaterial= ma.vray
	
	brdf_name= "BRDFDiffuse_no_material"

	textures= write_material_textures(ofile, {'material': ma,
									 'object':   ob,
									 'filters':  filters,
									 'uv_ids':   params.get('uv_ids') if params else None})

	if VRayMaterial.type == 'EMIT' and VRayMaterial.emitter_type == 'MESH':
		object_params['meshlight']['on']= True
		object_params['meshlight']['material']= ma
		# TODO: add more textures (shadow, etc)
		object_params['meshlight']['texture']= textures['mapto'].get('diffuse')
		return
	elif VRayMaterial.type == 'VOL':
		object_params['volume']= {}
		for param in OBJECT_PARAMS['EnvironmentFog']:
			if param == 'color':
				value= ma.diffuse_color
			else:
				value= getattr(VRayMaterial.EnvironmentFog,param)
			object_params['volume'][param]= value
		for param in ('color_tex','emission_tex','density_tex'):
			if param in textures['mapto']:
				object_params['volume'][param]= textures['mapto'][param]
		return

	if textures['values']['displacement_slot']:
		object_params['displace']['slot']=    textures['values']['displacement_slot']
		object_params['displace']['texture']= textures['mapto']['displacement']

	if ma in filters['exported_materials']:
		return
	else:
		filters['exported_materials'].append(ma)

	if VRayMaterial.type == 'MTL':
		if sce.vray.exporter.compat_mode:
		 	brdf_name= write_BRDF(ofile, sce, ma, ma_name, textures)
		else:
			brdf_name= write_BRDFVRayMtl(ofile, ma, ma_name, textures)
	elif VRayMaterial.type == 'SSS':
		brdf_name= write_BRDFSSS2Complex(ofile, ma, ma_name, textures['mapto'])
	elif VRayMaterial.type == 'EMIT' and VRayMaterial.emitter_type == 'MTL':
		brdf_name= write_BRDFLight(ofile, sce, ma, ma_name, textures)

	if VRayMaterial.type not in ('EMIT','VOL'):
		if textures['values']['normal_slot']:
			brdf_name= write_BRDFBump(ofile, brdf_name, textures)

	complex_material= []
	for component in (VRayMaterial.Mtl2Sided.use,VRayMaterial.MtlWrapper.use,VRayMaterial.MtlOverride.use,VRayMaterial.MtlRenderStats.use,VRayMaterial.material_id_number):
		if component:
			complex_material.append("MtlComp_%.2d_%s"%(len(complex_material), ma_name))
	complex_material.append(ma_name)
	complex_material.reverse()

	ofile.write("\nMtlSingleBRDF %s {"%(complex_material[-1]))
	#ofile.write("\n\tbrdf= %s;"%(a(sce,brdf_name)))
	ofile.write("\n\tbrdf= %s;" % brdf_name)
	ofile.write("\n}\n")

	if VRayMaterial.Mtl2Sided.use:
		base_material= complex_material.pop()
		ofile.write("\nMtl2Sided %s {"%(complex_material[-1]))
		ofile.write("\n\tfront= %s;"%(base_material))
		back= base_material
		if VRayMaterial.Mtl2Sided.back != "":
			if VRayMaterial.Mtl2Sided.back in bpy.data.materials:
				back= get_name(bpy.data.materials[VRayMaterial.Mtl2Sided.back],"Material")
		ofile.write("\n\tback= %s;"%(back))

		if VRayMaterial.Mtl2Sided.control == 'SLIDER':
			ofile.write("\n\ttranslucency= %s;" % a(sce, "Color(1.0,1.0,1.0)*%.3f" % VRayMaterial.Mtl2Sided.translucency_slider))
		elif VRayMaterial.Mtl2Sided.control == 'COLOR':
			ofile.write("\n\ttranslucency= %s;" % a(sce, VRayMaterial.Mtl2Sided.translucency_color))
		else:
			if VRayMaterial.Mtl2Sided.translucency_tex != "":
				if VRayMaterial.Mtl2Sided.translucency_tex in bpy.data.materials:
					ofile.write("\n\ttranslucency_tex= %s;"%(get_name(bpy.data.textures[VRayMaterial.Mtl2Sided.translucency_tex],"Texture")))
					ofile.write("\n\ttranslucency_tex_mult= %s;" % a(sce,VRayMaterial.Mtl2Sided.translucency_tex_mult))
			else:
				ofile.write("\n\ttranslucency= %s;" % a(sce, "Color(1.0,1.0,1.0)*%.3f" % VRayMaterial.Mtl2Sided.translucency_slider))

		ofile.write("\n\tforce_1sided= %d;" % VRayMaterial.Mtl2Sided.force_1sided)
		ofile.write("\n}\n")

	if VRayMaterial.MtlWrapper.use:
		base_material= complex_material.pop()
		ofile.write("\nMtlWrapper %s {"%(complex_material[-1]))
		ofile.write("\n\tbase_material= %s;"%(base_material))
		for param in OBJECT_PARAMS['MtlWrapper']:
			ofile.write("\n\t%s= %s;"%(param, a(sce,getattr(VRayMaterial.MtlWrapper,param))))
		ofile.write("\n}\n")

	if VRayMaterial.MtlOverride.use:
		base_mtl= complex_material.pop()
		ofile.write("\nMtlOverride %s {"%(complex_material[-1]))
		ofile.write("\n\tbase_mtl= %s;"%(base_mtl))

		for param in ('gi_mtl','reflect_mtl','refract_mtl','shadow_mtl'):
			override_material= getattr(VRayMaterial.MtlOverride, param)
			if override_material:
				if override_material in bpy.data.materials:
					ofile.write("\n\t%s= %s;"%(param, get_name(bpy.data.materials[override_material],"Material")))

		environment_override= VRayMaterial.MtlOverride.environment_override
		if environment_override:
			if environment_override in bpy.data.textures:
				ofile.write("\n\tenvironment_override= %s;" % get_name(bpy.data.textures[environment_override],"Texture"))

		ofile.write("\n\tenvironment_priority= %i;"%(VRayMaterial.MtlOverride.environment_priority))
		ofile.write("\n}\n")

	if VRayMaterial.MtlRenderStats.use:
		base_mtl= complex_material.pop()
		ofile.write("\nMtlRenderStats %s {"%(complex_material[-1]))
		ofile.write("\n\tbase_mtl= %s;"%(base_mtl))
		for param in OBJECT_PARAMS['MtlRenderStats']:
			ofile.write("\n\t%s= %s;"%(param, a(sce,getattr(VRayMaterial.MtlRenderStats,param))))
		ofile.write("\n}\n")

	if VRayMaterial.material_id_number:
		base_mtl= complex_material.pop()
		ofile.write("\nMtlMaterialID %s {"%(complex_material[-1]))
		ofile.write("\n\tbase_mtl= %s;" % base_mtl)
		ofile.write("\n\tmaterial_id_number= %i;" % VRayMaterial.material_id_number)
		#ofile.write("\n\tmaterial_id_color= %s;" % p(VRayMaterial.material_id_color))
		ofile.write("\n}\n")


def write_multi_material(ofile, ob):
	mtl_name= "Material_%s"%(get_name(ob,"Data"))

	mtls_list= []
	ids_list=  []

	for i,slot in enumerate(ob.material_slots):
		ma_name= "Material_no_material"
		if slot.material is not None:
			ma_name= get_name(slot.material, 'Material')
			
		mtls_list.append(ma_name)
		ids_list.append(str(i + 1))

	ofile.write("\nMtlMulti %s {"%(mtl_name))
	ofile.write("\n\tmtls_list= List(%s);"%(','.join(mtls_list)))
	ofile.write("\n\tids_list= ListInt(%s);"%(','.join(ids_list)))
	ofile.write("\n}\n")

	return mtl_name

# 'VolumeVRayToon'
#   lineColor: color = Color(0, 0, 0), The color of cartoon line
#   widthType: integer = 0
#   lineWidth: float = 1.5
#   opacity: float = 1
#   hideInnerEdges: bool = false
#   normalThreshold: float = 0.7
#   overlapThreshold: float = 0.95
#   traceBias: float = 0.2
#   doSecondaryRays: bool = false
#   excludeType: integer = 0
#   excludeList: plugin, unlimited list
#   lineColor_tex: acolor texture
#   lineWidth_tex: float texture
#   opacity_tex: float texture
#   distortion_tex: float texture

def write_materials(ofile,ob,filters,object_params):
	uv_layers= object_params['uv_ids']

	if len(ob.material_slots):
		for slot in ob.material_slots:
			ma= slot.material
			if ma:
				if sce.vray.exporter.use_material_nodes and ma.use_nodes and hasattr(ma.node_tree, 'links'):
					debug(sce,"Node materials temporarily disabled...")
					#write_node_material(params)
				write_material(ma, filters, object_params, ofile, ob= ob, params= {'uv_ids': uv_layers})

	ma_name= "Material_no_material"
	if len(ob.material_slots):
		if len(ob.material_slots) == 1:
			if ob.material_slots[0].material is not None:
				ma_name= get_name(ob.material_slots[0].material, "Material")
		else:
			ma_name= write_multi_material(ofile, ob)
	return ma_name


def generate_object_list(object_names_string= None, group_names_string= None):
	object_list= []

	if object_names_string:
		ob_names= object_names_string.split(';')
		for ob_name in ob_names:
			if ob_name in bpy.data.objects:
				object_list.append(bpy.data.objects[ob_name])

	if group_names_string:
		gr_names= group_names_string.split(';')
		for gr_name in gr_names:
			if gr_name in bpy.data.groups:
				object_list.extend(bpy.data.groups[gr_name].objects)

	return object_list


def write_visible_from_view(ofile, name, base_mtl, params):
	return ma_name


def write_node(ofile,name,geometry,material,object_id,visible,transform_matrix,ob,params):
	visibility= params['visibility']

	lights= []
	for lamp in [ob for ob in sce.objects if ob.type == 'LAMP']:
		VRayLamp= lamp.data.vray
		lamp_name= get_name(lamp,"Light")
		if not object_on_visible_layers(sce,lamp) or lamp.hide_render:
			if not sce.vray.use_hidden_lights:
				continue
		if VRayLamp.use_include_exclude:
			object_list= generate_object_list(VRayLamp.include_objects,VRayLamp.include_groups)
			if VRayLamp.include_exclude == 'INCLUDE':
				if ob in object_list:
					lights.append(lamp_name)
			else:
				if ob not in object_list:
					lights.append(lamp_name)
		else:
			lights.append(lamp_name)

	lights.extend(mesh_lights)
	
	base_mtl= material
	if sce.vray.SettingsOptions.mtl_override_on and sce.vray.SettingsOptions.mtl_override:
		base_mtl= get_name(bpy.data.materials[sce.vray.SettingsOptions.mtl_override],"Material")

	material= "HFV%s" % (name)

	ofile.write("\nMtlRenderStats %s {" % material)
	ofile.write("\n\tbase_mtl= %s;" % base_mtl)
	ofile.write("\n\tvisibility= %s;" % (0 if ob in visibility['all'] or visible == False else 1))
	ofile.write("\n\tcamera_visibility= %s;" % (0 if ob in visibility['camera'] else 1))
	ofile.write("\n\tgi_visibility= %s;" % (0 if ob in visibility['gi'] else 1))
	ofile.write("\n\treflections_visibility= %s;" % (0 if ob in visibility['reflect'] else 1))
	ofile.write("\n\trefractions_visibility= %s;" % (0 if ob in visibility['refract'] else 1))
	ofile.write("\n\tshadows_visibility= %s;" % (0 if ob in visibility['shadows'] else 1))
	ofile.write("\n}\n")

	ofile.write("\nNode %s {"%(name))
	ofile.write("\n\tobjectID= %d;" % (params['objectID'] if 'objectID' in params else object_id))
	ofile.write("\n\tgeometry= %s;"%(geometry))
	ofile.write("\n\tmaterial= %s;"%(material))
	ofile.write("\n\ttransform= %s;"%(a(sce,transform(transform_matrix))))
	ofile.write("\n\tlights= List(%s);"%(','.join(lights)))
	ofile.write("\n}\n")


def write_object(ob, params, add_params= None):
	props= {
		'filters': None,
		'types':   None,
		'files':   None,

		'material': None,
		'visible':  True,

		'dupli':        False,
		'dupli_group':  False,
		'dupli_name':   None,

		'matrix': None,
	}

	for key in params:
		props[key]= params[key]

	if add_params is not None:
		for key in add_params:
			props[key]= add_params[key]

	ofile= props['files']['nodes']

	types= props['types']
	files= props['files']

	object_params= {
		'meshlight': {
			'on':       False,
			'material': None
		},
		'displace': {
			'object':   ob,
			'texture':  None,
			'params':   None
		},
		'volume': None,
		'uv_ids': params.get('uv_ids'),
	}

	debug(sce, "  Params: %s" % object_params)

	VRayExporter= sce.vray.exporter
	VRayObject=   ob.vray
	VRayData=     ob.data.vray

	node_name= get_name(ob, "Node", dupli_name= props['dupli_name'])

	ma_name= "Material_no_material"

	if props['material'] is not None:
		# Don't override proxy material (proxy could have multi-material)
		if hasattr(VRayData,'GeomMeshFile') and VRayData.GeomMeshFile.use:
			ma_name= write_materials(props['files']['materials'],ob,props['filters'],object_params)
		else:
			ma_name= props['material']
	else:
		ma_name= write_materials(props['files']['materials'],ob,props['filters'],object_params)

	node_geometry= get_name(ob, "ME")
	if VRayExporter.use_instances:
		node_geometry= get_name(ob.data, "ME")

	if hasattr(VRayData,'GeomMeshFile') and VRayData.GeomMeshFile.use:
		node_geometry= write_mesh_file(ofile, props['filters']['exported_proxy'], ob)

	if object_params['displace']['texture'] and VRayExporter.use_displace:
		node_geometry= write_mesh_displace(ofile, node_geometry, object_params['displace'])

	node_matrix= ob.matrix_world
	if props['matrix'] is not None:
		if props['dupli_group']:
			node_matrix= props['matrix'] * ob.matrix_world
		else:
			node_matrix= props['matrix']

	if object_params['meshlight']['on']:
		write_LightMesh(files['lamps'], ob, object_params['meshlight'], node_name, node_geometry, node_matrix)
		return

	if object_params['volume'] is not None:
		if ma_name not in types['volume'].keys():
			types['volume'][ma_name]= {}
			types['volume'][ma_name]['params']= object_params['volume']
			types['volume'][ma_name]['gizmos']= []
		if ob not in types['volume'][ma_name]:
			types['volume'][ma_name]['gizmos'].append(write_EnvFogMeshGizmo(files['nodes'], node_name, node_geometry, node_matrix))
		return

	complex_material= []
	complex_material.append(ma_name)
	for component in (VRayObject.MtlWrapper.use,VRayObject.MtlOverride.use,VRayObject.MtlRenderStats.use):
		if component:
			complex_material.append("ObjComp_%.2d_%s"%(len(complex_material), ma_name))
	complex_material.reverse()

	if VRayObject.MtlWrapper.use:
		base_material= complex_material.pop()
		ma_name= complex_material[-1]
		ofile.write("\nMtlWrapper %s {"%(ma_name))
		ofile.write("\n\tbase_material= %s;"%(base_material))
		for param in OBJECT_PARAMS['MtlWrapper']:
			ofile.write("\n\t%s= %s;"%(param, a(sce,getattr(VRayObject.MtlWrapper,param))))
		ofile.write("\n}\n")

	if VRayObject.MtlOverride.use:
		base_mtl= complex_material.pop()
		ma_name= complex_material[-1]
		ofile.write("\nMtlOverride %s {"%(ma_name))
		ofile.write("\n\tbase_mtl= %s;"%(base_mtl))

		for param in ('gi_mtl','reflect_mtl','refract_mtl','shadow_mtl'):
			override_material= getattr(VRayObject.MtlOverride, param)
			if override_material:
				if override_material in bpy.data.materials:
					ofile.write("\n\t%s= %s;"%(param, get_name(bpy.data.materials[override_material],"Material")))

		environment_override= VRayObject.MtlOverride.environment_override
		if environment_override:
			if environment_override in bpy.data.materials:
				ofile.write("\n\tenvironment_override= %s;" % get_name(bpy.data.textures[environment_override],"Texture"))

		ofile.write("\n\tenvironment_priority= %i;"%(VRayObject.MtlOverride.environment_priority))
		ofile.write("\n}\n")

	if VRayObject.MtlRenderStats.use:
		base_mtl= complex_material.pop()
		ma_name= complex_material[-1]
		ofile.write("\nMtlRenderStats %s {"%(ma_name))
		ofile.write("\n\tbase_mtl= %s;"%(base_mtl))
		for param in OBJECT_PARAMS['MtlRenderStats']:
			ofile.write("\n\t%s= %s;"%(param, a(sce,getattr(VRayObject.MtlRenderStats,param))))
		ofile.write("\n}\n")

	if len(ob.particle_systems):
		for ps in ob.particle_systems:
			if ps.settings.use_render_emitter:
				write_node(ofile,node_name,node_geometry,ma_name,ob.pass_index,props['visible'],node_matrix,ob,params)
				break
	else:
		write_node(ofile,node_name,node_geometry,ma_name,ob.pass_index,props['visible'],node_matrix,ob,params)


def write_environment(ofile, volumes= None):
	wo= sce.world

	bg_tex= None
	gi_tex= None
	reflect_tex= None
	refract_tex= None

	bg_tex_mult= 1.0
	gi_tex_mult= 1.0
	reflect_tex_mult= 1.0
	refract_tex_mult= 1.0

	for slot in wo.texture_slots:
		if slot and slot.texture and slot.texture.type in TEX_TYPES:
			VRaySlot= slot.texture.vray_slot

			params= {'slot': slot,
					 'texture': slot.texture,
					 'environment': True,
					 'rotate': {'angle': VRaySlot.texture_rotation_h,
								'axis': 'Z'}}

			if slot.use_map_blend:
				bg_tex= write_texture(ofile, sce, params)
				bg_tex_mult= slot.blend_factor
			if slot.use_map_horizon:
				gi_tex= write_texture(ofile, sce, params)
				gi_tex_mult= slot.horizon_factor
			if slot.use_map_zenith_up:
				reflect_tex= write_texture(ofile, sce, params)
				reflect_tex_mult= slot.zenith_up_factor
			if slot.use_map_zenith_down:
				refract_tex=  write_texture(ofile, sce, params)
				refract_tex_mult= slot.zenith_down_factor

	ofile.write("\nSettingsEnvironment {")

	ofile.write("\n\tbg_color= %s;"%(a(sce,wo.vray.bg_color)))
	if bg_tex:
		ofile.write("\n\tbg_tex= %s;"%(bg_tex))
		ofile.write("\n\tbg_tex_mult= %s;"%(a(sce,bg_tex_mult)))

	if wo.vray.gi_override:
		ofile.write("\n\tgi_color= %s;"%(a(sce,wo.vray.gi_color)))
	if gi_tex:
		ofile.write("\n\tgi_tex= %s;"%(gi_tex))
		ofile.write("\n\tgi_tex_mult= %s;"%(a(sce,gi_tex_mult)))

	if wo.vray.reflection_override:
		ofile.write("\n\treflect_color= %s;"%(a(sce,wo.vray.reflection_color)))
	if reflect_tex:
		ofile.write("\n\treflect_tex= %s;"%(reflect_tex))
		ofile.write("\n\treflect_tex_mult= %s;"%(a(sce,reflect_tex_mult)))

	if wo.vray.refraction_override:
		ofile.write("\n\trefract_color= %s;"%(a(sce,wo.vray.refraction_color)))
	if refract_tex:
		ofile.write("\n\trefract_tex= %s;"%(refract_tex))
		ofile.write("\n\trefract_tex_mult= %s;"%(a(sce,refract_tex_mult)))

	if volumes:
		ofile.write("\n\tenvironment_volume= List(%s);"%(','.join(volumes)))

	ofile.write("\n}\n")


def write_EnvironmentFog(ofile,volume,material):
	LIGHT_MODE= {
		'ADDGIZMO':    4,
		'INTERGIZMO':  3,
		'OVERGIZMO':   2,
		'PERGIZMO':    1,
		'NO':          0
	}

	plugin= 'EnvironmentFog'
	name= "%s_%s" % (plugin,material)

	ofile.write("\n%s %s {"%(plugin,name))
	ofile.write("\n\tgizmos= List(%s);" % ','.join(volume[material]['gizmos']))
	for param in volume[material]['params']:
		if param == 'light_mode':
			value= LIGHT_MODE[volume[material]['params'][param]]
		elif param in ('density_tex','fade_out_tex','emission_mult_tex'):
			value= "%s::out_intensity" % volume[material]['params'][param]
		else:
			value= volume[material]['params'][param]
		ofile.write("\n\t%s= %s;"%(param, a(sce,value)))
	ofile.write("\n}\n")

	return name


def write_EnvFogMeshGizmo(ofile, node_name, node_geometry, node_matrix):
	plugin= 'EnvFogMeshGizmo'
	name= "%s_%s" % (plugin,node_name)

	ofile.write("\n%s %s {"%(plugin,name))
	ofile.write("\n\ttransform= %s;" % a(sce,transform(node_matrix)))
	ofile.write("\n\tgeometry= %s;" % node_geometry)
	#ofile.write("\n\tlights= %s;" % )
	#ofile.write("\n\tfade_out_radius= %s;" % )
	ofile.write("\n}\n")

	return name


def write_LightMesh(ofile, ob, params, name, geometry, matrix):
	plugin= 'LightMesh'

	ma=  params['material']
	tex= params['texture']

	light= getattr(ma.vray,plugin)

	ofile.write("\n%s %s {" % (plugin,name))
	ofile.write("\n\ttransform= %s;"%(a(sce,transform(matrix))))
	for param in OBJECT_PARAMS[plugin]:
		if param == 'color':
			if tex:
				ofile.write("\n\tcolor= %s;" % a(sce,ma.diffuse_color))
				ofile.write("\n\ttex= %s;" % tex)
				ofile.write("\n\tuse_tex= 1;")
			else:
				ofile.write("\n\tcolor= %s;"%(a(sce,ma.diffuse_color)))
		elif param == 'geometry':
			ofile.write("\n\t%s= %s;"%(param, geometry))
		elif param == 'units':
			ofile.write("\n\t%s= %i;"%(param, UNITS[light.units]))
		elif param == 'lightPortal':
			ofile.write("\n\t%s= %i;"%(param, LIGHT_PORTAL[light.lightPortal]))
		else:
			ofile.write("\n\t%s= %s;"%(param, a(sce,getattr(light,param))))
	ofile.write("\n}\n")


def write_lamp(ob, params, add_params= None):
	ofile= params['files']['lamps']
	
	lamp= ob.data
	vl= lamp.vray

	lamp_type= None
	lamp_name= get_name(ob,"Light")
	lamp_matrix= ob.matrix_world

	textures= write_lamp_textures(ofile, {'lamp': lamp})['mapto']

	if add_params is not None:
		if 'dupli_name' in add_params:
			lamp_name= "%s_%s" % (add_params['dupli_name'],lamp_name)
		if 'matrix' in add_params:
			lamp_matrix= add_params['matrix']

	if lamp.type == 'POINT':
		if vl.radius > 0:
			lamp_type= 'LightSphere'
		else:
			lamp_type= 'LightOmni'
	elif lamp.type == 'SPOT':
		if vl.spot_type == 'SPOT':
			lamp_type= 'LightSpot'
		else:
			lamp_type= 'LightIES'
	elif lamp.type == 'SUN':
		if vl.direct_type == 'DIRECT':
			lamp_type= 'LightDirectMax'
		else:
			lamp_type= 'SunLight'
	elif lamp.type == 'AREA':
		lamp_type= 'LightRectangle'
	elif lamp.type == 'HEMI':
		lamp_type= 'LightDome'
	else:
		return

	ofile.write("\n%s %s {"%(lamp_type,lamp_name))

	if 'color' in textures:
		ofile.write("\n\tcolor_tex= %s;" % textures['color'])

		if lamp.type == 'SUN' and vl.direct_type == 'DIRECT':
			ofile.write("\n\tprojector_map= %s;" % textures['color'])

		if lamp.type == 'AREA':
			ofile.write("\n\trect_tex= %s;" % textures['color'])
		elif lamp.type == 'HEMI':
			ofile.write("\n\tdome_tex= %s;" % textures['color'])

		if lamp.type in ('AREA','HEMI'):
			ofile.write("\n\tuse_rect_tex= 1;")
			ofile.write("\n\ttex_adaptive= %.2f;" % (1.0))
			ofile.write("\n\ttex_resolution= %i;" % (512))

	if 'intensity' in textures:
		ofile.write("\n\tintensity_tex= %s;" % a(sce, "%s::out_intensity" % textures['intensity']))

	if 'shadowColor' in textures:
		if lamp.type == 'SUN' and vl.direct_type == 'DIRECT':
			ofile.write("\n\tshadowColor_tex= %s;" % textures['shadowColor'])
		else:
			ofile.write("\n\tshadow_color_tex= %s;" % textures['shadowColor'])
		
	if lamp_type == 'SunLight':
		ofile.write("\n\tsky_model= %i;"%(SKY_MODEL[vl.sky_model]))
	else:
		ofile.write("\n\tcolor= %s;"%(a(sce,"Color(%.6f, %.6f, %.6f)"%(tuple(lamp.color)))))
		if lamp_type != 'LightIES':
			ofile.write("\n\tunits= %i;"%(UNITS[vl.units]))

	if lamp_type == 'LightSpot':
		ofile.write("\n\tconeAngle= %s;" % a(sce,lamp.spot_size))
		ofile.write("\n\tpenumbraAngle= %s;" % a(sce, - lamp.spot_size * lamp.spot_blend))

	if lamp_type == 'LightRectangle':
		if lamp.shape == 'RECTANGLE':
			ofile.write("\n\tu_size= %s;"%(a(sce,lamp.size/2)))
			ofile.write("\n\tv_size= %s;"%(a(sce,lamp.size_y/2)))
		else:
			ofile.write("\n\tu_size= %s;"%(a(sce,lamp.size/2)))
			ofile.write("\n\tv_size= %s;"%(a(sce,lamp.size/2)))
		ofile.write("\n\tlightPortal= %i;"%(LIGHT_PORTAL[vl.lightPortal]))

	for param in OBJECT_PARAMS[lamp_type]:
		if param == 'shadow_subdivs':
			ofile.write("\n\tshadow_subdivs= %s;"%(a(sce,vl.subdivs)))
		elif param == 'shadowRadius' and lamp_type == 'LightDirectMax':
			ofile.write("\n\t%s= %s;" % (param, a(sce,vl.shadowRadius)))
			ofile.write("\n\tshadowRadius1= %s;" % a(sce,vl.shadowRadius))
			ofile.write("\n\tshadowRadius2= %s;" % a(sce,vl.shadowRadius))
		elif param == 'intensity' and lamp_type == 'LightIES':
			ofile.write("\n\tpower= %s;"%(a(sce,vl.intensity)))
		elif param == 'shadow_color':
			ofile.write("\n\tshadow_color= %s;"%(a(sce,vl.shadowColor)))
		elif param == 'ies_file':
			ofile.write("\n\t%s= \"%s\";"%(param,get_full_filepath(sce,lamp,vl.ies_file)))
		else:
			ofile.write("\n\t%s= %s;"%(param, a(sce,getattr(vl,param))))

	ofile.write("\n\ttransform= %s;"%(a(sce,transform(lamp_matrix))))
	ofile.write("\n}\n")


def write_camera(sce, ofile, camera= None, bake= False):
	def get_distance(ob1, ob2):
		vec= ob1.location - ob2.location
		return vec.length
		
	def get_lens_shift(ob):
		camera= ob.data
		shift= 0.0
		constraint= None
		if len(ob.constraints) > 0:
			for co in ob.constraints:
				if co.type in ('TRACK_TO','DAMPED_TRACK','LOCKED_TRACK'):
					constraint= co
					break
		if constraint:
			constraint_ob= constraint.target
			if constraint_ob:
				z_shift= ob.location[2] - constraint_ob.location[2]
				x= ob.location[0] - constraint_ob.location[0]
				y= ob.location[1] - constraint_ob.location[1]
				l= math.sqrt( x * x + y * y )
				shift= -1 * z_shift / l
		else:
			rx= ob.rotation_euler[0]
			lsx= rx - math.pi / 2
			if math.fabs(lsx) > 0.0001:
				shift= math.tan(lsx)
			if math.fabs(shift) > math.pi:
				shift= 0.0
		return shift

	ca= camera if camera is not None else sce.camera

	if ca is not None:
		VRayCamera= ca.data.vray
		SettingsCamera= VRayCamera.SettingsCamera
		CameraPhysical= VRayCamera.CameraPhysical

		wx= sce.render.resolution_x * sce.render.resolution_percentage / 100
		wy= sce.render.resolution_y * sce.render.resolution_percentage / 100

		aspect= float(wx) / float(wy)

		fov= ca.data.angle
		if VRayCamera.override_fov:
			fov= VRayCamera.fov
			
		if aspect < 1.0:
			fov= fov * aspect

		if bake:
			VRayBake= sce.vray.VRayBake
			bake_ob= None
		
			if VRayBake.object in bpy.data.objects:
				bake_ob= bpy.data.objects[VRayBake.object]

			if bake_ob:
				ofile.write("\nUVWGenChannel UVWGenChannel_BakeView {")
				ofile.write("\n\tuvw_transform=Transform(")
				ofile.write("\n\t\tMatrix(")
				ofile.write("\n\t\tVector(1.0,0.0,0.0),")
				ofile.write("\n\t\tVector(0.0,1.0,0.0),")
				ofile.write("\n\t\tVector(0.0,0.0,1.0)")
				ofile.write("\n\t\t),")
				ofile.write("\n\t\tVector(0.0,0.0,0.0)")
				ofile.write("\n\t);")
				ofile.write("\n\tuvw_channel=1;")
				ofile.write("\n}\n")
				ofile.write("\nBakeView {")
				ofile.write("\n\tbake_node= %s;" % get_name(bake_ob,"Node"))
				ofile.write("\n\tbake_uvwgen= UVWGenChannel_BakeView;")
				ofile.write("\n\tdilation= %i;" % VRayBake.dilation)
				ofile.write("\n\tflip_derivs= %i;" % VRayBake.flip_derivs)
				ofile.write("\n}\n")
			else:
				print("V-Ray/Blender: Error! No object selected for baking!")

		else:
			ofile.write("\nRenderView RenderView {")
			ofile.write("\n\ttransform= %s;"%(a(sce,transform(ca.matrix_world))))
			ofile.write("\n\tfov= %s;"%(a(sce,fov)))
			if SettingsCamera.type != 'SPHERIFICAL':
				ofile.write("\n\tclipping= 1;")
				ofile.write("\n\tclipping_near= %s;"%(a(sce,ca.data.clip_start)))
				ofile.write("\n\tclipping_far= %s;"%(a(sce,ca.data.clip_end)))
			if ca.data.type == 'ORTHO':
				ofile.write("\n\torthographic= 1;")
				ofile.write("\n\torthographicWidth= %s;" % a(sce,ca.data.ortho_scale))
			ofile.write("\n}\n")

		ofile.write("\nSettingsCamera Camera {")
		if ca.data.type == 'ORTHO':
			ofile.write("\n\ttype= 7;")
			ofile.write("\n\theight= %s;" % a(sce,ca.data.ortho_scale))
		else:
			ofile.write("\n\ttype= %i;"%(CAMERA_TYPE[SettingsCamera.type]))
		ofile.write("\n\tfov= %s;"%(a(sce,fov)))
		ofile.write("\n}\n")

		focus_distance= ca.data.dof_distance
		if ca.data.dof_object:
			focus_distance= get_distance(ca,ca.data.dof_object)

		if focus_distance < 0.001:
			focus_distance= 200.0

		if CameraPhysical.use:
			ofile.write("\nCameraPhysical PhysicalCamera_%s {" % clean_string(ca.name))
			ofile.write("\n\ttype= %d;"%(PHYS[CameraPhysical.type]))
			ofile.write("\n\tspecify_focus= 1;")
			ofile.write("\n\tfocus_distance= %s;"%(a(sce,focus_distance)))
			# ofile.write("\n\ttargeted= 1;")
			# ofile.write("\n\ttarget_distance= %s;"%(a(sce,focus_distance)))
			ofile.write("\n\tspecify_fov= %i;" % CameraPhysical.specify_fov)
			ofile.write("\n\tfov= %s;"%(a(sce,fov)))
			ofile.write("\n\twhite_balance= %s;"%(a(sce,"Color(%.3f,%.3f,%.3f)"%(tuple(CameraPhysical.white_balance)))))
			for param in OBJECT_PARAMS['CameraPhysical']:
				if param == 'lens_shift' and CameraPhysical.guess_lens_shift:
					value= get_lens_shift(ca)
				else:
					value= getattr(CameraPhysical,param)
				ofile.write("\n\t%s= %s;"%(param, a(sce,value)))
			ofile.write("\n}\n")


def write_settings(sce,ofile):
	rd= sce.render
	
	VRayScene=    sce.vray
	VRayExporter= VRayScene.exporter
	VRayDR=       VRayScene.VRayDR
	
	ofile.write("// V-Ray/Blender %s\n"%(VERSION))
	ofile.write("// Settings\n\n")

	for f in ('materials', 'lights', 'nodes', 'camera'):
		if VRayDR.on:
			if VRayDR.type == 'UU':
				ofile.write("#include \"%s\"\n" % get_filenames(sce,f))
			elif VRayDR.type == 'WU':
				ofile.write("#include \"%s\"\n" % (os.path.join(os.path.normpath(bpy.path.abspath(VRayDR.shared_dir)),os.path.split(bpy.data.filepath)[1][:-6],os.path.basename(get_filenames(sce,f)))))
			else:
				ofile.write("#include \"%s\"\n" % (os.path.join(os.path.normpath(bpy.path.abspath(VRayDR.shared_dir)),os.path.split(bpy.data.filepath)[1][:-6],os.path.basename(get_filenames(sce,f)))))
		else:
			ofile.write("#include \"%s\"\n"%(os.path.basename(get_filenames(sce,f))))

	for t in range(rd.threads):
		ofile.write("#include \"%s_%.2i.vrscene\"\n" % (os.path.basename(get_filenames(sce,'geometry'))[:-11], t))

	wx= rd.resolution_x * rd.resolution_percentage / 100
	wy= rd.resolution_y * rd.resolution_percentage / 100

	ofile.write("\nSettingsOutput {")
	ofile.write("\n\timg_separateAlpha= %d;"%(0))
	ofile.write("\n\timg_width= %s;"%(int(wx)))
	if VRayScene.VRayBake.use:
		ofile.write("\n\timg_height= %s;"%(int(wx)))
	else:
		ofile.write("\n\timg_height= %s;"%(int(wy)))
	if VRayExporter.animation:
		ofile.write("\n\timg_file= \"render_%s.%s\";" % (clean_string(sce.camera.name),get_render_file_format(VRayExporter,rd.file_format)))
		ofile.write("\n\timg_dir= \"%s\";"%(get_filenames(sce,'output')))
		ofile.write("\n\timg_file_needFrameNumber= 1;")
		ofile.write("\n\tanim_start= %d;"%(sce.frame_start))
		ofile.write("\n\tanim_end= %d;"%(sce.frame_end))
		ofile.write("\n\tframe_start= %d;"%(sce.frame_start))
		ofile.write("\n\tframes_per_second= %d;"%(1.0) )
		ofile.write("\n\tframes= %d-%d;"%(sce.frame_start, sce.frame_end))
	ofile.write("\n\tframe_stamp_enabled= %d;"%(0))
	ofile.write("\n\tframe_stamp_text= \"%s\";"%("vb25 (git) | V-Ray Standalone %%vraycore | %%rendertime"))
	ofile.write("\n}\n")

	module= VRayScene.SettingsImageSampler
	if module.filter_type != 'NONE':
		ofile.write(AA_FILTER_TYPE[module.filter_type])
		ofile.write("\n\tsize= %.3f;"%(module.filter_size))
		ofile.write("\n}\n")

	for module in MODULES:
		vmodule= getattr(VRayScene, module)

		ofile.write("\n%s {"%(module))
		if module == 'SettingsImageSampler':
			ofile.write("\n\ttype= %d;"%(IMAGE_SAMPLER_TYPE[vmodule.type]))
		elif module == 'SettingsColorMapping':
			ofile.write("\n\ttype= %d;"%(COLOR_MAPPING_TYPE[vmodule.type]))
		elif module == 'SettingsRegionsGenerator':
			ofile.write("\n\tseqtype= %d;"%(SEQTYPE[vmodule.seqtype]))
			ofile.write("\n\txymeans= %d;"%(XYMEANS[vmodule.xymeans]))

		for param in MODULES[module]:
			ofile.write("\n\t%s= %s;"%(param, p(getattr(vmodule, param))))
		ofile.write("\n}\n")

	for plugin in SETTINGS_PLUGINS:
		if hasattr(plugin,'write'):
			rna_pointer= getattr(VRayScene,plugin.PLUG)
			plugin.write(ofile,sce,rna_pointer)

	dmc= VRayScene.SettingsDMCSampler
	gi=  VRayScene.SettingsGI
	im=  VRayScene.SettingsGI.SettingsIrradianceMap
	lc=  VRayScene.SettingsGI.SettingsLightCache
	bf=  VRayScene.SettingsGI.SettingsDMCGI
	if gi.on:
		ofile.write("\nSettingsGI {")
		ofile.write("\n\ton= 1;")
		ofile.write("\n\tprimary_engine= %s;"%(PRIMARY[gi.primary_engine]))
		ofile.write("\n\tsecondary_engine= %s;"%(SECONDARY[gi.secondary_engine]))
		ofile.write("\n\tprimary_multiplier= %s;"%(gi.primary_multiplier))
		ofile.write("\n\tsecondary_multiplier= %s;"%(gi.secondary_multiplier))
		ofile.write("\n\treflect_caustics= %s;"%(p(gi.reflect_caustics)))
		ofile.write("\n\trefract_caustics= %s;"%(p(gi.refract_caustics)))
		ofile.write("\n\tsaturation= %.6f;"%(gi.saturation))
		ofile.write("\n\tcontrast= %.6f;"%(gi.contrast))
		ofile.write("\n\tcontrast_base= %.6f;"%(gi.contrast_base))
		ofile.write("\n}\n")

		ofile.write("\nSettingsIrradianceMap {")
		ofile.write("\n\tmin_rate= %i;"%(im.min_rate))
		ofile.write("\n\tmax_rate= %i;"%(im.max_rate))
		ofile.write("\n\tsubdivs= %i;"%(im.subdivs))
		ofile.write("\n\tinterp_samples= %i;"%(im.interp_samples))
		ofile.write("\n\tinterp_frames= %i;"%(im.interp_frames))
		ofile.write("\n\tcalc_interp_samples= %i;"%(im.calc_interp_samples))
		ofile.write("\n\tcolor_threshold= %.6f;"%(im.color_threshold))
		ofile.write("\n\tnormal_threshold= %.6f;"%(im.normal_threshold))
		ofile.write("\n\tdistance_threshold= %.6f;"%(im.distance_threshold))
		ofile.write("\n\tdetail_enhancement= %i;"%(im.detail_enhancement))
		ofile.write("\n\tdetail_radius= %.6f;"%(im.detail_radius))
		ofile.write("\n\tdetail_subdivs_mult= %.6f;"%(im.detail_subdivs_mult))
		ofile.write("\n\tdetail_scale= %i;"%(SCALE[im.detail_scale]))
		ofile.write("\n\tinterpolation_mode= %i;"%(INT_MODE[im.interpolation_mode]))
		ofile.write("\n\tlookup_mode= %i;"%(LOOK_TYPE[im.lookup_mode]))
		ofile.write("\n\tshow_calc_phase= %i;"%(im.show_calc_phase))
		ofile.write("\n\tshow_direct_light= %i;"%(im.show_direct_light))
		ofile.write("\n\tshow_samples= %i;"%(im.show_samples))
		ofile.write("\n\tmultipass= %i;"%(im.multipass))
		ofile.write("\n\tcheck_sample_visibility= %i;"%(im.check_sample_visibility))
		ofile.write("\n\trandomize_samples= %i;"%(im.randomize_samples))
		ofile.write("\n\tmode= %d;"%(IM_MODE[im.mode]))
		ofile.write("\n\tauto_save= %d;"%(im.auto_save))
		ofile.write("\n\tauto_save_file= \"%s\";"%(bpy.path.abspath(im.auto_save_file)))
		ofile.write("\n\tfile= \"%s\";"%(bpy.path.abspath(im.file)))
		ofile.write("\n\tdont_delete= false;")
		ofile.write("\n}\n")

		ofile.write("\nSettingsDMCGI {")
		ofile.write("\n\tsubdivs= %i;"%(bf.subdivs))
		ofile.write("\n\tdepth= %i;"%(bf.depth))
		ofile.write("\n}\n")

		ofile.write("\nSettingsLightCache {")
		ofile.write("\n\tsubdivs= %.0f;"%(lc.subdivs * dmc.subdivs_mult))
		ofile.write("\n\tsample_size= %.6f;"%(lc.sample_size))
		ofile.write("\n\tnum_passes= %i;"% (rd.threads if lc.num_passes_auto else lc.num_passes))
		ofile.write("\n\tdepth= %i;"%(lc.depth))
		ofile.write("\n\tfilter_type= %i;"%(LC_FILT[lc.filter_type]))
		ofile.write("\n\tfilter_samples= %i;"%(lc.filter_samples))
		ofile.write("\n\tfilter_size= %.6f;"%(lc.filter_size))
		ofile.write("\n\tprefilter= %i;"%(lc.prefilter))
		ofile.write("\n\tprefilter_samples= %i;"%(lc.prefilter_samples))
		ofile.write("\n\tshow_calc_phase= %i;"%(lc.show_calc_phase))
		ofile.write("\n\tstore_direct_light= %i;"%(lc.store_direct_light))
		ofile.write("\n\tuse_for_glossy_rays= %i;"%(lc.use_for_glossy_rays))
		ofile.write("\n\tworld_scale= %i;"%(SCALE[lc.world_scale]))
		ofile.write("\n\tadaptive_sampling= %i;"%(lc.adaptive_sampling))
		ofile.write("\n\tmode= %d;"%(LC_MODE[lc.mode]))
		ofile.write("\n\tauto_save= %d;"%(lc.auto_save))
		ofile.write("\n\tauto_save_file= \"%s\";"%(bpy.path.abspath(lc.auto_save_file)))
		ofile.write("\n\tfile= \"%s\";"%(bpy.path.abspath(lc.file)))
		ofile.write("\n\tretrace_enabled= %d;"%(lc.retrace_enabled))
		ofile.write("\n\tretrace_threshold= %.3f;"%(lc.retrace_threshold))
		ofile.write("\n\tdont_delete= false;")
		ofile.write("\n}\n")

	ofile.write("\nSettingsEXR {")
	ofile.write("\n\tcompression= 0;") # 0 - default, 1 - no compression, 2 - RLE, 3 - ZIPS, 4 - ZIP, 5 - PIZ, 6 - pxr24
	ofile.write("\n\tbits_per_channel= %d;" % (16 if rd.use_exr_half else 32))
	ofile.write("\n}\n")

	ofile.write("\nSettingsJPEG SettingsJPEG {")
	ofile.write("\n\tquality= %d;" % rd.file_quality)
	ofile.write("\n}\n")

	ofile.write("\nSettingsPNG SettingsPNG {")
	ofile.write("\n\tcompression= %d;" % int(rd.file_quality / 10))
	ofile.write("\n\tbits_per_channel= 16;")
	ofile.write("\n}\n")

	# ofile.write("\nRTEngine {")
	# ofile.write("\n\tseparate_window= 1;")
	# ofile.write("\n\ttrace_depth= 3;")
	# ofile.write("\n\tuse_gi= 1;")
	# ofile.write("\n\tgi_depth= 3;")
	# ofile.write("\n\tgi_reflective_caustics= 1;")
	# ofile.write("\n\tgi_refractive_caustics= 1;")
	# ofile.write("\n\tuse_opencl= 1;")
	# ofile.write("\n}\n")	

	for channel in VRayScene.render_channels:
		plugin= get_plugin(CHANNEL_PLUGINS, channel.type)
		if plugin:
			plugin.write(ofile, getattr(channel,plugin.PLUG), sce, channel.name)

	ofile.write("\n")


def write_scene(sce, bake= False):
	global mesh_lights

	# Reset mesh lights list
	mesh_lights= []
	
	VRayScene= sce.vray
	VRayExporter=    VRayScene.exporter
	SettingsOptions= VRayScene.SettingsOptions

	ca= sce.camera
	VRayCamera= ca.data.vray
	vc= VRayCamera.SettingsCamera

	files= {
		'lamps':     open(get_filenames(sce,'lights'), 'w'),
		'materials': open(get_filenames(sce,'materials'), 'w'),
		'nodes':     open(get_filenames(sce,'nodes'), 'w'),
		'camera':    open(get_filenames(sce,'camera'), 'w'),
		'scene':     open(get_filenames(sce,'scene'), 'w')
	}

	types= {
		'volume': {}
	}

	for key in files:
		files[key].write("// V-Ray/Blender %s\n" % VERSION)

	files['materials'].write("// Materials\n")
	files['materials'].write("\n// Default materials")
	files['materials'].write("\nUVWGenChannel UVWGenChannel_default {")
	files['materials'].write("\n\tuvw_channel= 1;")
	files['materials'].write("\n\tuvw_transform= Transform(")
	files['materials'].write("\n\t\tMatrix(")
	files['materials'].write("\n\t\t\tVector(1.0,0.0,0.0),")
	files['materials'].write("\n\t\t\tVector(0.0,1.0,0.0),")
	files['materials'].write("\n\t\t\tVector(0.0,0.0,1.0)")
	files['materials'].write("\n\t\t),")
	files['materials'].write("\n\t\tVector(0.0,0.0,0.0)")
	files['materials'].write("\n\t);")
	files['materials'].write("\n}\n")
	files['materials'].write("\nTexChecker Texture_Test_Checker {")
	files['materials'].write("\n\tuvwgen= UVWGenChannel_default;")
	files['materials'].write("\n}\n")
	files['materials'].write("\nTexChecker Texture_no_texture {")
	files['materials'].write("\n\tuvwgen= UVWGenChannel_default;")
	files['materials'].write("\n}\n")
	files['materials'].write("\nBRDFDiffuse BRDFDiffuse_no_material {")
	files['materials'].write("\n\tcolor=Color(0.5, 0.5, 0.5);")
	files['materials'].write("\n}\n")
	files['materials'].write("\nMtlSingleBRDF Material_no_material {")
	files['materials'].write("\n\tbrdf= BRDFDiffuse_no_material;")
	files['materials'].write("\n}\n")
	files['materials'].write("\nTexAColor TexAColor_default_blend {")
	files['materials'].write("\n\tuvwgen= UVWGenChannel_default;")
	files['materials'].write("\n\ttexture= AColor(1.0,1.0,1.0,1.0);")
	files['materials'].write("\n}\n")
	files['materials'].write("\n// Scene materials\n")
	files['nodes'].write("// Nodes\n")
	files['lamps'].write("// Lights\n")
	files['camera'].write("// Camera & Environment\n")

	def _write_object_particles(ob, params, add_params= None):
		if len(ob.particle_systems):
			for ps in ob.particle_systems:
				ps_material= "Material_no_material"
				ps_material_idx= ps.settings.material
				if ps_material_idx <= len(ob.material_slots):
					ps_material= get_name(ob.material_slots[ps_material_idx - 1].material, "Material")

				if ps.settings.type == 'HAIR' and ps.settings.render_type == 'PATH':
					if VRayExporter.use_hair:
						hair_geom_name= "HAIR_%s" % ps.name
						hair_node_name= "%s_%s" % (ob.name,hair_geom_name)

						write_GeomMayaHair(params['files']['nodes'],ob,ps,hair_geom_name)
						write_node(params['files']['nodes'], hair_node_name, hair_geom_name, ps_material, ob.pass_index, True, ob.matrix_world, ob, params)
				else:
					particle_objects= []
					if ps.settings.render_type == 'OBJECT':
						particle_objects.append(ps.settings.dupli_object)
					elif ps.settings.render_type == 'GROUP':
						particle_objects= ps.settings.dupli_group.objects
					else:
						continue

					for p,particle in enumerate(ps.particles):
						if PLATFORM == "linux2":
							sys.stdout.write("V-Ray/Blender: Object: \033[0;33m%s\033[0m => Particle: \033[0;32m%i\033[0m\r" % (ob.name, p))
						else:
							sys.stdout.write("V-Ray/Blender: Object: %s => Particle: %i\r" % (ob.name, p))
						sys.stdout.flush()
						
						location= particle.location
						size= particle.size
						if ps.settings.type == 'HAIR':
							location= particle.hair[0].co
							size*= 3

						part_transform= mathutils.Matrix.Scale(size, 3) * particle.rotation.to_matrix()
						part_transform.resize_4x4()
						part_transform[3][0]= location[0]
						part_transform[3][1]= location[1]
						part_transform[3][2]= location[2]

						for p_ob in particle_objects:
							part_name= "PS%sPA%s" % (clean_string(ps.name), p)
							if add_params is not None:
								if 'dupli_name' in add_params:
									part_name= '_'.join([add_params['dupli_name'],clean_string(ps.name),str(p)])
									
							if ps.settings.use_whole_group or ps.settings.use_global_dupli:
								part_transform= part_transform * p_ob.matrix_world

							part_visibility= True
							if ps.settings.type == 'EMITTER':
								part_visibility= True if particle.alive_state not in ('DEAD','UNBORN') else False

							_write_object(p_ob, params, {'dupli': True,
														 'dupli_name': part_name,
														 'visible': part_visibility,
														 'material': ps_material,
														 'matrix': part_transform})

	def _write_object_dupli(ob, params, add_params= None):
		if ob.dupli_type in ('VERTS','FACES','GROUP'):
			ob.create_dupli_list(sce)
			for dup_id,dup_ob in enumerate(ob.dupli_list):
				dup_name= "%s_%s" % (ob.name,dup_id)
				if ob.pass_index:
					params['objectID']= ob.pass_index
				_write_object(dup_ob.object, params, {'dupli': True,
													  'dupli_name': dup_name,
													  'matrix': dup_ob.matrix})
				if 'objectID' in params:
					del params['objectID']
			ob.free_dupli_list()

	def _write_object(ob, params, add_params= None):
		if ob.type in ('CAMERA','ARMATURE','LATTICE'):
			return
		if ob.type == 'LAMP':
			write_lamp(ob,params,add_params)
		elif ob.type == 'EMPTY':
			_write_object_dupli(ob,params,add_params)
		else:
			_write_object_particles(ob,params,add_params)
			_write_object_dupli(ob,params,add_params)
			write_object(ob,params,add_params)

	def write_frame(camera= None):
		params= {
			'scene': sce,
			'camera': camera,
			'files': files,
			'filters': {
				'exported_bitmaps':   [],
				'exported_textures':  [],
				'exported_materials': [],
				'exported_proxy':     [],
			},
			'types': types,
			'uv_ids': get_uv_layers(sce),
		}

		if camera:
			VRayCamera= ca.data.vray

			visibility= {
				'all':     [],
				'camera':  [],
				'gi':      [],
				'reflect': [],
				'refract': [],
				'shadows': [],
			}

			if VRayCamera.hide_from_view:
				for hide_type in visibility:
					if getattr(VRayCamera, 'hf_%s' % hide_type):
						if getattr(VRayCamera, 'hf_%s_auto' % hide_type):
							visibility[hide_type]= generate_object_list(group_names_string= 'hf_%s' % ca.name)
						else:
							visibility[hide_type]= generate_object_list(getattr(VRayCamera, 'hf_%s_objects' % hide_type), getattr(VRayCamera, 'hf_%s_groups' % hide_type))

			params['visibility']= visibility
			debug(sce, "Hide from view: %s" %  visibility)

		write_environment(params['files']['camera'])
		write_camera(sce,params['files']['camera'],bake= bake)

		for ob in sce.objects:
			if ob.type in ('CAMERA','ARMATURE','LATTICE'):
				continue

			if VRayExporter.active_layers:
				if not object_on_visible_layers(sce,ob):
					if not SettingsOptions.geom_doHidden:
						continue
				
			if ob.hide_render:
				if not SettingsOptions.geom_doHidden:
					continue

			for slot in ob.material_slots:
				if slot.material:
					VRayMaterial= slot.material.vray
					print(ob.name, VRayMaterial.type)
					if VRayMaterial.type == 'EMIT' and VRayMaterial.emitter_type == 'MESH':
						node_name= get_name(ob,"Node")
						if node_name not in mesh_lights:
							mesh_lights.append(node_name)


		for ob in sce.objects:
			if ob.type in ('CAMERA','ARMATURE','LATTICE'):
				continue

			if VRayExporter.active_layers:
				if not object_on_visible_layers(sce,ob):
					if ob.type == 'LAMP':
						if VRayScene.use_hidden_lights:
							pass
					elif SettingsOptions.geom_doHidden:
						pass
					else:
						continue

			if ob.hide_render:
				if ob.type == 'LAMP':
					if not VRayScene.use_hidden_lights:
						continue
				else:
					if not SettingsOptions.geom_doHidden:
						continue
		
			debug(sce,"[%s]: %s"%(ob.type,ob.name))
			debug(sce,"  Animated: %d"%(1 if ob.animation_data else 0))
			if hasattr(ob,'data'):
				if ob.data:
					debug(sce,"  Data animated: %d"%(1 if ob.data.animation_data else 0))
			if not VRayExporter.debug:
				if PLATFORM == "linux2":
					sys.stdout.write("V-Ray/Blender: [%d] %s: \033[0;32m%s\033[0m                              \r"%(sce.frame_current, ob.type, ob.name))
				else:
					sys.stdout.write("V-Ray/Blender: [%d] %s: %s                              \r"%(sce.frame_current, ob.type, ob.name))
				sys.stdout.flush()

			_write_object(ob, params)

		del params

	sys.stdout.write("V-Ray/Blender: Writing scene...\n")
	timer= time.clock()

	if VRayExporter.animation:
		selected_frame= sce.frame_current
		f= sce.frame_start
		while(f <= sce.frame_end):
			sce.frame_set(f)
			write_frame(ca)
			f+= sce.frame_step
		sce.frame_set(selected_frame)
	else:
		write_frame(ca)

	if len(types['volume']):
		write_environment(files['nodes'],[write_EnvironmentFog(files['nodes'],types['volume'],vol) for vol in types['volume']])

	write_settings(sce,files['scene'])

	for key in files:
		files[key].write("\n// vim: set syntax=on syntax=c:\n\n")
		files[key].close()

	sys.stdout.write("V-Ray/Blender: Writing scene done. [%.2f]                    \n" % (time.clock() - timer))
	sys.stdout.flush()



'''
  V-Ray Renderer
'''
class VRAY_OT_create_proxy(bpy.types.Operator):
	bl_idname      = "vray.create_proxy"
	bl_label       = "Create proxy"
	bl_description = "Creates proxy from selection."

	def execute(self, context):
		sce= context.scene
		timer= time.clock()

		def _create_proxy(ob):
			GeomMeshFile= ob.data.vray.GeomMeshFile

			vrmesh_filename= GeomMeshFile.filename if GeomMeshFile.filename else clean_string(ob.name)
			vrmesh_filename+= ".vrmesh"

			vrmesh_dirpath= bpy.path.abspath(GeomMeshFile.dirpath)
			if not os.path.exists(vrmesh_dirpath):
				os.mkdir(vrmesh_dirpath)
			vrmesh_filepath= os.path.join(vrmesh_dirpath,vrmesh_filename)

			if GeomMeshFile.animation:
				selected_frame= sce.frame_current

				frame_start= sce.frame_start
				frame_end= sce.frame_end
				if GeomMeshFile.animation_range == 'MANUAL':
					frame_start= GeomMeshFile.frame_start
					frame_end= GeomMeshFile.frame_end

				# Export first frame to create file
				frame= frame_start
				sce.frame_set(frame)
				generate_proxy(sce,ob,vrmesh_filepath)
				frame+= 1
				# Export all other frames
				while(frame <= frame_end):
					sce.frame_set(frame)
					generate_proxy(sce,ob,vrmesh_filepath,append=True)
					frame+= 1
				sce.frame_set(selected_frame)
			else:
				generate_proxy(sce,ob,vrmesh_filepath)

			ob_name= ob.name
			ob_data_name= ob.data.name

			if GeomMeshFile.mode != 'NONE':
				if GeomMeshFile.mode in ('THIS','REPLACE'):
					if GeomMeshFile.add_suffix:
						ob.name+= '_proxy'
						ob.data.name+= '_proxy'

				if GeomMeshFile.mode == 'THIS':
					GeomMeshFile.use= True
					GeomMeshFile.file= bpy.path.relpath(vrmesh_filepath)

				bbox_faces= ((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7))
				bbox_mesh= bpy.data.meshes.new(ob_data_name+'_proxy')
				bbox_mesh.from_pydata(ob.bound_box, [], bbox_faces)
				bbox_mesh.update()

				if GeomMeshFile.mode in ('NEW','REPLACE'):
					for slot in ob.material_slots:
						if slot and slot.material:
							bbox_mesh.materials.append(slot.material)

				if GeomMeshFile.mode == 'NEW':
					new_ob= bpy.data.objects.new(ob_name+'_proxy', bbox_mesh)
					sce.objects.link(new_ob)
					new_ob.matrix_world= ob.matrix_world
					new_ob.draw_type= 'WIRE'
					bpy.ops.object.select_all(action='DESELECT')
					new_ob.select= True
					sce.objects.active= new_ob

					if GeomMeshFile.apply_transforms:
						ob.select= True
						sce.objects.active= ob
						bpy.ops.object.scale_apply()
						bpy.ops.object.rotation_apply()
						bpy.ops.object.location_apply()

					GeomMeshFile= new_ob.data.vray.GeomMeshFile
					GeomMeshFile.use= True
					GeomMeshFile.file= bpy.path.relpath(vrmesh_filepath)

				elif GeomMeshFile.mode == 'REPLACE':
					original_mesh= ob.data

					ob.data= bbox_mesh
					ob.draw_type= 'WIRE'
					for md in ob.modifiers: ob.modifiers.remove(md)

					if GeomMeshFile.apply_transforms:
						ob.select= True
						sce.objects.active= ob
						bpy.ops.object.scale_apply()
						bpy.ops.object.rotation_apply()
						bpy.ops.object.location_apply()

					GeomMeshFile= ob.data.vray.GeomMeshFile
					GeomMeshFile.use= True
					GeomMeshFile.file= bpy.path.relpath(vrmesh_filepath)

					bpy.data.meshes.remove(original_mesh)

		if len(bpy.context.selected_objects):
			for ob in bpy.context.selected_objects:
				_create_proxy(ob)
		else:
			_create_proxy(context.object)

		debug(context.scene, "Proxy generation total time: %.2f\n" % (time.clock() - timer))

		return{'FINISHED'}


class VRAY_OT_write_geometry(bpy.types.Operator):
	bl_idname      = "vray.write_geometry"
	bl_label       = "Export meshes"
	bl_description = "Export meshes."

	def execute(self, context):
		write_geometry(context.scene)
		return{'FINISHED'}


class VRayRenderer(bpy.types.RenderEngine):
	bl_idname      = 'VRAY_RENDER'
	bl_label       = "V-Ray (git)"
	bl_use_preview = False
	
	def render(self, scene):
		global sce

		sce= scene
		rd=  scene.render
		wo=  scene.world

		vsce= sce.vray
		ve= vsce.exporter
		dr= vsce.VRayDR

		VRayBake= vsce.VRayBake

		if ve.auto_meshes:
			write_geometry(sce)
		
		write_scene(sce, bake= VRayBake.use)

		vb_path= vb_script_path()

		params= []
		params.append(vb_binary_path(sce))

		image_file= os.path.join(get_filenames(sce,'output'),"render_%s.%s" % (clean_string(sce.camera.name),get_render_file_format(ve,rd.file_format)))
		load_file= os.path.join(get_filenames(sce,'output'),"render_%s.%.4i.%s" % (clean_string(sce.camera.name),sce.frame_current,get_render_file_format(ve,rd.file_format)))

		wx= rd.resolution_x * rd.resolution_percentage / 100
		wy= rd.resolution_y * rd.resolution_percentage / 100

		if rd.use_border:
			x0= wx * rd.border_min_x
			y0= wy * (1.0 - rd.border_max_y)
			x1= wx * rd.border_max_x
			y1= wy * (1.0 - rd.border_min_y)

			if rd.use_crop_to_border:
				params.append('-crop=')
			else:
				params.append('-region=')
			params.append("%i;%i;%i;%i"%(x0,y0,x1,y1))

		params.append('-sceneFile=')
		params.append(get_filenames(sce,'scene'))

		params.append('-display=')
		params.append('1')

		if ve.image_to_blender:
			params.append('-autoclose=')
			params.append('1')

		params.append('-frames=')
		if ve.animation:
			params.append("%d-%d,%d"%(sce.frame_start, sce.frame_end,int(sce.frame_step)))
		else:
			params.append("%d" % sce.frame_current)

		if dr.on:
			if len(dr.nodes):
				params.append('-distributed=')
				params.append('1')
				params.append('-portNumber=')
				params.append(str(dr.port))
				params.append('-renderhost=')
				params.append("\"%s\"" % ';'.join([n.address for n in dr.nodes]))
				
		params.append('-imgFile=')
		params.append(image_file)

		if ve.autorun:
			process= subprocess.Popen(params)

			if not ve.animation and ve.image_to_blender:
				while True:
					if self.test_break():
						try:
							process.kill()
						except:
							pass
						break

					if process.poll() is not None:
						try:
							result= self.begin_result(0, 0, int(wx), int(wy))
							result.layers[0].load_from_file(load_file)
							self.end_result(result)
						except:
							pass
						break

					time.sleep(0.05)
		else:
			print("V-Ray/Blender: Enable \"Autorun\" option to start V-Ray automatically after export.")
			print("V-Ray/Blender: Command: %s" % ' '.join(params))


class VRayRendererPreview(bpy.types.RenderEngine):
	bl_idname      = 'VRAY_RENDER_PREVIEW'
	bl_label       = "V-Ray (git) [material preview]"
	bl_use_preview = True
	
	def render(self, scene):
		global sce
		
		sce= scene
		rd=  scene.render
		wo=  scene.world

		vsce= sce.vray
		ve= vsce.exporter

		wx= int(rd.resolution_x * rd.resolution_percentage / 100)
		wy= int(rd.resolution_y * rd.resolution_percentage / 100)

		vb_path=   vb_script_path()
		vray_path= vb_binary_path(sce)

		params= []
		params.append(vray_path)

		if sce.name == "preview":
			if wx < 100:
				return

			image_file= os.path.join(get_filenames(sce,'output'),"preview.exr")
			load_file= image_file

			filters= {
				'exported_bitmaps':   [],
				'exported_materials': [],
				'exported_proxy':     []
			}

			temp_params= {
				'uv_ids': get_uv_layers(sce),
			}

			object_params= {
				'meshlight': {
					'on':       False,
					'material': None
				},
				'displace': {
					'texture':  None,
					'params':   None
				},
				'volume':       None,
			}

			ofile= open(os.path.join(vb_path,"preview","preview_materials.vrscene"), 'w')
			ofile.write("\nSettingsOutput {")
			ofile.write("\n\timg_separateAlpha= 0;")
			ofile.write("\n\timg_width= %s;" % wx)
			ofile.write("\n\timg_height= %s;" % wy)
			ofile.write("\n}\n")
			for ob in sce.objects:
				if ob.type == 'CAMERA':
					if ob.name == "Camera":
						write_camera(sce, ofile, camera= ob)
					continue
				if ob.type in ('CAMERA','LAMP','EMPTY','ARMATURE','LATTICE'):
					continue
				if object_on_visible_layers(sce,ob):
					continue
				for ms in ob.material_slots:
					if ms.material:
						if ob.name.find("preview") != -1:
							write_material(ms.material, filters, object_params, ofile, name="PREVIEW", ob= ob, params= temp_params)
						elif ms.material.name in ("checkerlight","checkerdark"):
							write_material(ms.material, filters, object_params, ofile, ob= ob, params= temp_params)
			ofile.close()

			params.append('-sceneFile=')
			params.append(os.path.join(vb_path,"preview","preview.vrscene"))
			params.append('-display=')
			params.append("0")
			params.append('-showProgress=')
			params.append("0")
			params.append('-imgFile=')
			params.append(image_file)

		else:
			image_file= os.path.join(get_filenames(sce,'output'),"render_%s.%s" % (clean_string(sce.camera.name),get_render_file_format(ve,rd.file_format)))
			load_file= os.path.join(get_filenames(sce,'output'),"render_%s.%.4i.%s" % (clean_string(sce.camera.name),sce.frame_current,get_render_file_format(ve,rd.file_format)))

			if ve.auto_meshes:
				bpy.ops.vray.write_geometry()
			write_scene(sce)

			if rd.use_border:
				x0= wx * rd.border_min_x
				y0= wy * (1.0 - rd.border_max_y)
				x1= wx * rd.border_max_x
				y1= wy * (1.0 - rd.border_min_y)

				region= "%i;%i;%i;%i"%(x0,y0,x1,y1)

				if(rd.use_crop_to_border):
					params.append('-crop=')
				else:
					params.append('-region=')
				params.append(region)

			params.append('-sceneFile=')
			params.append(get_filenames(sce,'scene'))

			params.append('-display=')
			params.append("1")

			if ve.image_to_blender:
				params.append('-autoclose=')
				params.append('1')

			if ve.animation:
				params.append('-frames=')
				params.append("%d-%d,%d"%(sce.frame_start, sce.frame_end,int(sce.frame_step)))
			else:
				params.append('-frames=')
				params.append("%d" % sce.frame_current)

			params.append('-imgFile=')
			params.append(image_file)

		if ve.autorun:
			process= subprocess.Popen(params)

			if not ve.animation and ve.image_to_blender or sce.name == "preview":
				while True:
					if self.test_break():
						try:
							process.kill()
						except:
							pass
						break

					if process.poll() is not None:
						try:
							result= self.begin_result(0, 0, wx, wy)
							layer= result.layers[0]
							layer.load_from_file(load_file)
							self.end_result(result)
						except:
							pass
						break

					time.sleep(0.05)
		else:
			print("V-Ray/Blender: Enable \"Autorun\" option to start V-Ray automatically after export.")
			print("V-Ray/Blender: Command: %s" % ' '.join(params))

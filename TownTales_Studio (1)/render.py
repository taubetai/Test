"""Blender procedural shot renderer. New scene and motion per shot, no video assets."""
import bpy, math, json, sys, random
from mathutils import Vector
from pathlib import Path
spec,out=sys.argv[sys.argv.index('--')+1:]; d=json.loads(Path(spec).read_text()); s=d['shot']; rng=random.Random(d['seed']); fps=30; frames=max(1,round(d['duration']*fps)); bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def mat(name,c,metal=0):
 m=bpy.data.materials.new(name); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=.63; p.inputs['Metallic'].default_value=metal; return m
def cube(name,loc,scale,m,parent=None):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object;o.name=name;o.dimensions=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m)
 if parent: o.parent=parent
 return o
def empty(name,loc):
 o=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(o);o.location=loc;return o
def sphere(name,loc,scale,m):
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,location=loc);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(m);return o
def key(o,frame,prop):o.keyframe_insert(data_path=prop,frame=frame)
def aim(o,pt):o.rotation_euler=(Vector(pt)-o.location).to_track_quat('-Z','Y').to_euler()
wood=mat('Wood',(.28,.15,.09)); wall=mat('Plaster',(.62,.57,.48)); road=mat('Asphalt',(.11,.13,.16)); grass=mat('Grass',(.16,.29,.15)); black=mat('Ink',(.025,.03,.04)); skin=mat('Skin',(.86,.58,.34)); hair=mat('Hair',(.52,.30,.08)); shirt=mat('Blue hoodie',(.1,.31,.65)); jeans=mat('Denim',(.10,.13,.23)); glass=mat('Glass blue',(.21,.51,.65),.35); white=mat('Paper',(.88,.87,.78)); red=mat('Warning',(.6,.05,.07)); foliage=mat('Leaves',(.12,.28,.15)); lamp=mat('Lamp',(.95,.71,.28)); loc=s.get('location','street'); time=s.get('time','night')
cube('Ground',(0,0,-.15),(40,40,.3),grass if loc in ('street','forest') else wood)
def tree(x,y):
 cube('Trunk',(x,y,1.2),(.4,.4,2.4),wood);sphere('Crown',(x,y,3),(1.25,1.25,1.6),foliage)
def house(x,y):
 c=mat('House',rng.choice([(.47,.35,.27),(.29,.43,.48),(.62,.52,.37)]));cube('House',(x,y,1.6),(4.3,3.8,3.2),c);o=cube('Roof',(x,y,3.35),(4.8,4.1,.5),road);cube('Door',(x,y-1.93,.95),(.8,.09,1.9),wood);cube('Window',(x+1.25,y-1.96,1.8),(1,.08,.85),glass)
if loc=='street':
 cube('Road',(0,0,.015),(5,40,.06),road)
 for y in range(-12,16,5):
  house(-5,y+3);house(5,y+3);cube('Road marking',(0,y,.07),(.11,1.4,.025),white)
elif loc=='forest':
 for i in range(32):
  x,y=rng.uniform(-10,10),rng.uniform(-3,15)
  if abs(x)>2 or y>5:tree(x,y)
else:
 cube('Back wall',(0,4,2),(12,.2,4),wall);cube('Side wall',(-5,0,2),(.2,10,4),wall);cube('Baseboard',(0,3.85,.17),(12,.12,.3),wood)
 if loc=='bedroom':cube('Bed',(-2,2,.45),(1.5,2.7,.65),wood);cube('Blanket',(-2,2,.83),(1.5,2.6,.18),shirt)
 if loc in ('classroom','shop'): 
  for x in [-3,0,3]:cube('Counter',(x,2,.65),(1.6,.8,1.3),wood)
 if loc=='hallway':
  for x in [-3,0,3]:cube('Hall door',(x,3.85,1.3),(1.1,.1,2.6),wood)
def person(name,x,y,tall=False):
 root=empty(name,(x,y,0)); k=1.35 if tall else 1; col=black if tall else shirt; face=mat('Stranger skin',(.57,.55,.52)) if tall else skin
 def part(n,p,sz,m):return cube(n,p,sz,m,root)
 part('Torso',(0,0,1.35*k),(.68,.4,.78*k),col);part('Head',(0,0,2.02*k),(.62,.55,.57*k),face);part('Hair',(0,0,2.29*k),(.65,.56,.15),black if tall else hair)
 for sign in [-1,1]:part('Eye',(sign*.13,-.282,2.08*k),(.065,.018,.1),black)
 part('Mouth',(0,-.282,1.90*k),(.18,.018,.04 if s.get('action')!='shock' else .11),black)
 limbs=[]
 for sign in [-1,1]:
  shoulder=empty('Shoulder',(sign*.47,0,1.67*k));shoulder.parent=root;cube('Arm',(0,0,-.33*k),(.24,.28,.66*k),col,shoulder);cube('Hand',(0,0,-.7*k),(.24,.27,.16),face,shoulder);hip=empty('Hip',(sign*.19,0,.93*k));hip.parent=root;cube('Leg',(0,0,-.39*k),(.31,.34,.78*k),jeans if not tall else black,hip);cube('Shoe',(0,-.07,-.81*k),(.34,.47,.18),black,hip);limbs.append((shoulder,hip))
 act=s.get('action','idle'); moving=act in ('walk','run'); root.location.y=y;key(root,1,'location');root.location.y=y-(1.6 if act=='walk' else 3 if act=='run' else .05);key(root,frames,'location');
 for f in range(1,frames+1,3):
  phase=(f-1)/fps*(10 if act=='run' else 6); 
  for i,(arm,leg) in enumerate(limbs):
   sign=1 if i==0 else -1; arm.rotation_euler.x=sign*math.sin(phase)*(.65 if moving else .025);leg.rotation_euler.x=-arm.rotation_euler.x if moving else 0
   if act in ('reach','shock','hide'):arm.rotation_euler.x=(-1.2 if act=='reach' else -1.7)*min(1,f/12);arm.rotation_euler.y=sign*.25
   key(arm,f,'rotation_euler');key(leg,f,'rotation_euler')
  if act in ('turn','look'):root.rotation_euler.z=.65*math.sin(f/frames*math.pi);key(root,f,'rotation_euler')
 return root
who=s.get('character','main'); hero=person('Stranger' if who=='stranger' else 'Lucas',0,0,who=='stranger');
if who=='both':person('Stranger',1.7,1.1,True)
def val(v,lo,hi,default=0):
 try:return max(lo,min(hi,float(v)))
 except:return default
for p in s.get('props',[])[:12]:
 if not isinstance(p,dict):continue
 k=p.get('kind','custom');x=val(p.get('x'),-3,3);y=val(p.get('y'),-2,4);z=val(p.get('z'),0,2);scale=val(p.get('size'),.3,2,1);name=str(p.get('name',k))[:50];color=p.get('color','#887766');
 try:c=tuple(int(color[i:i+2],16)/255 for i in (1,3,5));m=mat(name,c)
 except:m=wood
 if k=='tree':tree(x,y);continue
 if k in ('door','mirror','window'):
  cube(name+' frame',(x,y,z+scale),(.9*scale,.15,2*scale),wood);cube(name,(x,y-.09,z+scale),(.76*scale,.06,1.83*scale),glass if k in ('mirror','window') else m)
 elif k in ('letter','book','phone','key','sign'):
  cube(name,(x,y,z+.55),(.6*scale,.09,.38*scale),white if k=='letter' else m)
  if k=='letter':
   for i in range(3):cube('Ink line',(x,y-.052,z+.48+i*.07),(.36*scale,.01,.017),black)
 elif k in ('clock','lamp'):
  cube(name,(x,y,z+.8),(.12,.12,1.6),wood);sphere(name+' head',(x,y,z+1.7),(.3*scale,.3*scale,.3*scale),lamp if k=='lamp' else white)
 else:cube(name,(x,y,z+.45*scale),(scale,scale*.65,scale*.9),m)
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.world.color=(.25,.25,.25) if time=='day' else (.055,.07,.13)
def light(name,xyz,power,c,size):
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.color=c;data.shape='DISK';data.size=size;o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);o.location=xyz;aim(o,(0,0,1))
light('Key',(2,-4,6),1500 if time=='day' else 800,(1,.84,.64) if time=='day' else (1,.14,.13) if time=='red' else (.48,.66,1),4);light('Rim',(-3,4,5),1000,(.5,.68,1) if time!='red' else (1,.1,.08),3);light('Fill',(0,-4,3),350,(1,.9,.83),4)
if time=='day':
 data=bpy.data.lights.new('Sun','SUN');data.energy=2;obj=bpy.data.objects.new('Sun',data);scene.collection.objects.link(obj);obj.rotation_euler=(.55,-.45,-.6)
camdata=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',camdata);scene.collection.objects.link(cam);scene.camera=cam;style=s.get('camera','wide');positions={'wide':((4,-9,4),(0,0,1.3),35),'close':((.8,-4,2.35),(0,0,1.9),50),'low':((2,-5,.6),(0,0,1.8),38),'overhead':((3,-5,7),(0,0,1),37),'tracking':((3,-6,2.9),(0,0,1.45),40)};p,target,lens=positions.get(style,positions['wide']);cam.location=p;aim(cam,target);camdata.lens=lens;key(cam,1,'location');key(cam,1,'rotation_euler');cam.location=Vector(p)+Vector((.35,.4 if style!='tracking' else -1.1,.08));aim(cam,(target[0],target[1]-(.8 if s.get('action') in ('walk','run') else 0),target[2]));key(cam,frames,'location');key(cam,frames,'rotation_euler');camdata.dof.use_dof=style=='close';camdata.dof.focus_object=hero;camdata.dof.aperture_fstop=5.6
scene.render.resolution_x=d['width'];scene.render.resolution_y=d['height'];scene.render.resolution_percentage=100;scene.render.fps=fps;scene.frame_start=1;scene.frame_end=frames;scene.render.image_settings.file_format='FFMPEG';scene.render.ffmpeg.format='MPEG4';scene.render.ffmpeg.codec='H264';scene.render.ffmpeg.constant_rate_factor='MEDIUM';scene.render.filepath=out;scene.render.use_file_extension=False;bpy.ops.render.render(animation=True)

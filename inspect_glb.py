import struct
import json

with open('frontend/assets/heart.glb', 'rb') as f:
    magic, version, length = struct.unpack('<4sII', f.read(12))
    print(f'GLB Magic: {magic}, Version: {version}, Length: {length}')
    chunk_len, chunk_type = struct.unpack('<I4s', f.read(8))
    print(f'Chunk 0: {chunk_type}, Length: {chunk_len}')
    json_bytes = f.read(chunk_len)
    gltf = json.loads(json_bytes.decode('utf-8'))

print('\n--- GLTF Summary ---')
print('Nodes count:', len(gltf.get('nodes', [])))
print('Meshes count:', len(gltf.get('meshes', [])))
print('Skins count:', len(gltf.get('skins', [])))
print('Animations count:', len(gltf.get('animations', [])))

print('\n--- Nodes ---')
for idx, node in enumerate(gltf.get('nodes', [])):
    n_name = node.get('name', '')
    mesh = node.get('mesh')
    skin = node.get('skin')
    children = node.get('children', [])
    print(f'Node [{idx}]: "{n_name}" | mesh={mesh} | skin={skin} | children={children}')

if gltf.get('skins'):
    print('\n--- Skins ---')
    for idx, skin in enumerate(gltf.get('skins', [])):
        s_name = skin.get('name', '')
        joints = skin.get('joints', [])
        joint_names = [gltf['nodes'][j].get('name', str(j)) for j in joints]
        print(f'Skin [{idx}]: "{s_name}"')
        for j_idx, j_name in zip(joints, joint_names):
            print(f'   Joint node {j_idx}: "{j_name}"')

if gltf.get('animations'):
    print('\n--- Animations ---')
    for idx, anim in enumerate(gltf.get('animations', [])):
        a_name = anim.get('name', '')
        channels = anim.get('channels', [])
        samplers = anim.get('samplers', [])
        print(f'Anim [{idx}]: "{a_name}" | channels={len(channels)} | samplers={len(samplers)}')
        # Check duration
        max_time = 0.0
        min_time = 0.0
        for s in samplers:
            input_acc_idx = s['input']
            acc = gltf['accessors'][input_acc_idx]
            if 'max' in acc:
                max_time = max(max_time, acc['max'][0])
            if 'min' in acc:
                min_time = min(min_time, acc['min'][0])
        print(f'   Duration: {min_time}s to {max_time}s')

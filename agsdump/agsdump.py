import sys
import os
import json
import datetime

from slugify import slugify
from mapservice import MapService
from layer import Layer

reload(sys)
sys.setdefaultencoding('utf8')

def main():
    if len(sys.argv) != 3:
        print('Usage: agsdump map_name map_url')
        exit(1)
    else:
        map_name = sys.argv[1]
        map_url = sys.argv[2]

    # dump_styles(map_name, map_url)
    dump_data(map_name, map_url)

def dump_styles(map_name, map_url):

    # get dump folder
    dump_folder = get_dump_folder(map_name, 'styles')

    # initialize map service
    map_service = MapService(map_url)

    for layer in map_service.layers:
        layer_id = layer.get('id')
        layer_name = slugify(layer.get('name')).replace("-", "_")
        layer_name = layer.get('name')
        print("\n{} {}".format(layer_id, layer_name))

        layer = Layer(map_url, layer_id, dump_folder)

        layer.dump_sld_file()

def dump_data(map_name, map_url):

    # get dump folder
    dump_folder = get_dump_folder(map_name, 'data')

    # initialize map service
    map_service = MapService(map_url)

    for layer in map_service.layers:
        layer_id = layer.get('id')
        layer_name = slugify(layer.get('name')).replace("-", "_")
        layer_name = layer.get('name')

        suffix = '.json'
        layer_file = os.path.join(dump_folder, layer_name + suffix)
        
        feat_count = map_service.get(layer_id, count_only=True)
        
        print("\n{}. {} ({})".format(layer_id, layer_name, feat_count))
    
        if feat_count > 0:
            x = datetime.datetime.now()
            print '     Start: ', x
            layer_data = map_service.get(layer_id)

            with open(layer_file, 'w') as f:
                json.dump(layer_data, f)

            x = datetime.datetime.now()
            print '    Finish: ', x

def get_dump_folder(map_name, sub_folder):
    # create dump folder if it does not exist
    # return the path to the calling function

    dirpath = os.getcwd()
    dump_folder = os.path.join(dirpath, map_name, sub_folder)
    if not os.path.exists(dump_folder):
        os.makedirs(dump_folder)

    return dump_folder
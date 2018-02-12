#!/usr/bin/env python
__author__ = "Gao Wang"
__copyright__ = "Copyright 2016, Stephens lab"
__email__ = "gaow@uchicago.edu"
__license__ = "MIT"
import os, msgpack, glob, pickle
import pandas as pd
from .utils import uniq_list, chunks, OrderedDict, remove_multiple_strings, extend_dict, remove_quotes, DBError
from .addict import Dict as dotdict

def remove_obsolete_output(output, additional_files = None, rerun = False):
    from sos.__main__ import cmd_remove
    map_db = '{}/{}.map.mpk'.format(output, os.path.basename(output))
    # Load existing file names
    if os.path.isfile(map_db) and not rerun:
        map_data = msgpack.unpackb(open(map_db, 'rb').read(), encoding = 'utf-8',
                                   object_pairs_hook = OrderedDict)
    else:
        map_data = OrderedDict()
    # Remove file signature when files are deleted
    to_remove = []
    for k, x in list(map_data.items()):
        x = os.path.join(output, x)
        if not (os.path.isfile(x) or os.path.isfile(x + '.zapped')):
            to_remove.append(x)
            del map_data[k]
    # Remove files that are not in the name database
    for x in glob.glob('{}/*'.format(output)):
        if x.endswith(".zapped"):
            x = x[:-7]
            x_ext = '.zapped'
        else:
            x_ext = ''
        if os.path.basename(x) not in map_data.values() and \
           x not in ['{}/{}.{}.mpk'.format(output, os.path.basename(output), i) for i in ['conf', 'map']] and \
           x != '{}/{}.db'.format(output, os.path.basename(output)):
            to_remove.append(x + x_ext)
    # Additional files to remove
    for x in additional_files or []:
        if not os.path.isfile(x):
            to_remove.append(x)
    if rerun:
        to_remove = list(glob.glob('.sos/.dsc/{}_*.mpk'.format(os.path.basename(output)))) + to_remove
    if len(to_remove):
        open(map_db, "wb").write(msgpack.packb(map_data))
        # Do not limit to tracked or untracked, and do not just remove signature
        cmd_remove(dotdict({"tracked": False, "untracked": False,
                            "targets": to_remove, "external": True,
                            "__confirm__": True, "signature": False,
                            "verbosity": 0, "zap": False,
                            "size": None, "age": None, "dryrun": False}), [])
    if rerun and os.path.isfile('.sos/.dsc/{}.lib-info'.format(os.path.basename(output))):
        os.remove('.sos/.dsc/{}.lib-info'.format(os.path.basename(output)))

def build_config_db(io_db, map_db, conf_db, vanilla = False, jobs = 4):
    '''
    - collect all output file names in md5 style
    - check if map file should be loaded, and load it
    - update map file: remove irrelevant entries; add new file name mapping (starting from max index)
    - create conf file based on map file and io file
    '''
    def get_names():
        '''Get map names.'''
        # names has to be ordered dict to make sure
        # map_data is updated non-randomly
        # return is a list of original name and new name mapping
        names = OrderedDict()
        lookup = dict()
        base_ids = dict()
        # 1. collect sequence names and hash
        for k in list(data.keys()):
            for kk in data[k]:
                if kk in ["DSC_EXT_", "DSC_IO_"]:
                    continue
                kk = kk.split(' ')[0]
                if kk in names:
                    raise ValueError(f'\nIdentical modules found: ``{kk}``!')
                content = uniq_list(reversed([x for x in chunks(kk.split(":"), 2)]))
                # content example:
                # [('rcauchy', '71c60831e6ac5e824cb845171bd19933'),
                # ('mean', 'dfb0dd672bf5d91dd580ac057daa97b9'),
                # ('MSE', '0657f03051e0103670c6299f9608e939')]
                k_core = tuple([x[0] for x in content])
                if not k_core in base_ids:
                    base_ids[k_core] = dict([(x, 0) for x in k_core])
                if not k_core in lookup:
                    lookup[k_core] = dict()
                if kk in map_data:
                    # same module signature already exist
                    # will not work on the name map of these
                    # but will have to find their max ids
                    # so that we know how to properly name new comers
                    # ie we count how many times each of the module has occured
                    # in this particular sequence
                    ids = os.path.splitext(remove_multiple_strings(map_data[kk], kk.split(':')[::2]))[0]
                    ids = [int(s) for s in ids.split('_') if s.isdigit()]
                    for i, x in enumerate(base_ids[k_core].keys()):
                        base_ids[k_core][x] = max(base_ids[k_core][x], ids[i])
                    names[kk] = map_data[kk]
                else:
                    lookup[k_core] = extend_dict(lookup[k_core], dict(content), unique = True)
                    names[kk] = content
                    names[kk].append(data[k]["DSC_EXT_"])
        for k in names:
            # existing items in map_data, skip them
            if isinstance(names[k], str):
                continue
            # new items to be processed
            k_core = dict(names[k][:-1])
            key = tuple(k_core.keys())
            # 2. replace the hash with an ID
            new_name = []
            for kk in k_core:
                new_name.append(f'{kk}_{base_ids[key][kk] + lookup[key][kk].index(k_core[kk]) + 1}')
            # 3. construct name map
            names[k] = '_'.join(new_name) + f'.{names[k][-1]}'
        return names

    def update_map(names):
        '''Update maps and write to disk'''
        map_data.update(names)
        open(map_db, "wb").write(msgpack.packb(map_data))

    #
    if os.path.isfile(map_db) and not vanilla:
        map_data = msgpack.unpackb(open(map_db, 'rb').read(), encoding = 'utf-8',
                                   object_pairs_hook = OrderedDict)
    else:
        map_data = OrderedDict()
    data = msgpack.unpackb(open(io_db, 'rb').read(), encoding = 'utf-8',
                           object_pairs_hook = OrderedDict)
    meta_data = msgpack.unpackb(open(io_db[:-4] + '.meta.mpk', 'rb').read(), encoding = 'utf-8',
                                object_pairs_hook = OrderedDict)
    map_names = get_names()
    update_map(map_names)
    fid = os.path.dirname(str(conf_db))
    conf = OrderedDict()
    for key in meta_data:
        workflow_id = str(key)
        if workflow_id not in conf:
            conf[workflow_id] = OrderedDict()
        for module in meta_data[key]:
            k = f'{module}:{key}'
            if k not in data:
                k = f'{meta_data[key][module][0]}:{meta_data[key][module][1]}'
                # FIXME: this will be a bug if ever triggered
                if k not in data:
                    raise DBError(f"Cannot find key ``{k}`` in DSC I/O records.")
                conf[workflow_id][module] = (str(meta_data[key][module][1]), meta_data[key][module][0])
                continue
            if module not in conf[workflow_id]:
                conf[workflow_id][module] = OrderedDict()
            conf[workflow_id][module]['input'] = [os.path.join(fid, map_data[item]) \
                                        for item in data[k]['DSC_IO_'][0]]
            conf[workflow_id][module]['output'] = [os.path.join(fid, map_data[item]) \
                                         for item in data[k]['DSC_IO_'][1]]
            # eg. score_beta:6cf79a4c4bf191ea:simulate:90d846d054f4b5d1:shrink:fde60bc16e1728c7:simulate:90d846d054f4b5d1
            conf[workflow_id][module]['depends'] = [meta_data[key][x]
                                                    for x in uniq_list(data[k]['DSC_IO_'][1][0].split(':')[::2][1:])]
    #
    open(conf_db, "wb").write(msgpack.packb(conf))

class ResultDB:
    def __init__(self, prefix, targets):
        self.prefix = prefix
        # when set to None uses the last modules of pipelines
        # as master tables
        self.targets = targets
        # master tables
        self.master = OrderedDict()
        # data: every module is a table
        self.data = OrderedDict()
        # modules that appear at the end of pipelines
        self.end_modules = []
        if os.path.isfile(f"{self.prefix}.map.mpk"):
            self.maps = msgpack.unpackb(open(f"{self.prefix}.map.mpk", "rb").read(), encoding = 'utf-8',
                                        object_pairs_hook = OrderedDict)
        else:
            raise DBError(f"Cannot build DSC meta-data: hash table ``{self.prefix}.map.mpk`` is missing!")
        self.meta_kws = ['ID', 'MID', 'FILE', 'PARENT', '__out_vars__']

    def load_parameters(self):
        #
        def search_dependent_index(x):
            res = None
            for vv in self.data.values():
                try:
                    # FIXME: maybe slow here
                    res = vv['ID'][vv['MID'].index(x)]
                    break
                except ValueError:
                    continue
            if res is None:
                raise DBError(f'Cannot find the queried dependency module instance ``{x}``!')
            return res
        #
        def find_namemap(x):
            if x in self.maps:
                return self.maps[x][:-len_ext]
            raise DBError('Cannot find name map for ``{}``'.format(x))
        #
        try:
            self.rawdata = msgpack.unpackb(open(f'.sos/.dsc/{os.path.basename(self.prefix)}.io.mpk', 'rb').read(),
                                                encoding = 'utf-8', object_pairs_hook = OrderedDict)
            self.metadata = msgpack.unpackb(open(f'.sos/.dsc/{os.path.basename(self.prefix)}.io.meta.mpk', 'rb').read(),
                                                encoding = 'utf-8', object_pairs_hook = OrderedDict)
        except:
            raise DBError('Cannot load source data to build database!')
        # FIXME: make these to DSC keywords and check DSC keywords
        # by just loading it not redefining it here
        KWS = ['sequence_id', 'sequence_name', 'module', 'exec', '__out_vars__']
        # flatten dictionary removing duplicate keys because those keys are just `DSC_IO` and `DSC_EXT`
        # All other info in counts should be unique

        # from collections import Counter
        # counts =  Counter(key for sub in self.rawdata.values() for key in sub)
        # data = OrderedDict([(key, value) for sub in self.rawdata.values() for key, value in sub.items() if counts[key] == 1])
        #
        # total number of module instances involved
        # some instances can be identical
        inst_cnts = 0
        seen = []
        for workflow_id in self.metadata:
            workflow_len = len(self.metadata[workflow_id])
            for m_id, module in enumerate(self.metadata[workflow_id].keys()):
                pipeline_module = '{}:{}'.format(self.metadata[workflow_id][module][0], self.metadata[workflow_id][module][1])
                if pipeline_module in seen:
                    continue
                seen.append(pipeline_module)
                data = self.rawdata[pipeline_module]
                is_end_module = (m_id + 1) == workflow_len
                if self.targets is not None:
                    # For given target we must treat it as if it is end of a pipeline
                    # so that we can query from it
                    is_end_module = module in self.targets or is_end_module
                if not module in self.end_modules and is_end_module:
                    self.end_modules.append(module)
                #
                len_ext = len(data['DSC_EXT_']) + 1
                for k, v in data.items():
                    if k in ['DSC_IO_', 'DSC_EXT_']:
                        continue
                    inst_cnts += 1
                    # each v is a dict of a module instances
                    # each k reads like
                    # "shrink:a8bd873083994102:simulate:bd4946c8e9f6dcb6 simulate:bd4946c8e9f6dcb6"
                    # avoid name conflict
                    # FIXME: make these DSC keywords
                    #
                    if module in self.data:
                        keys1 = repr(sorted([x for x in v.keys() if not x in KWS]))
                        keys2 = repr(sorted([x for x in self.data[module].keys() if not x in self.meta_kws]))
                        if keys1 != keys2:
                            raise DBError('Inconsistent keys between module '\
                                          '``{0} ({1})`` and ``{2} ({3})``.'.\
                                          format(inst_cnts, keys1, self.data[module]['ID'], keys2))
                    else:
                        self.data[module] = dict()
                        for x in self.meta_kws:
                            self.data[module][x] = []
                        self.data[module]['__out_vars__'] = v['__out_vars__']
                    # ID numbers all module instances
                    self.data[module]['ID'].append(inst_cnts)
                    k = k.split(' ')
                    self.data[module]['MID'].append(k[0])
                    self.data[module]['FILE'].append(find_namemap(k[0]))
                    if len(k) > 1:
                        # Have to fine its ID ...
                        # If I trust the order of io.meta.mpk then I just search which
                        # module has MID == k[-1] and return its ID
                        self.data[module]['PARENT'].append(search_dependent_index(k[-1]))
                    else:
                        self.data[module]['PARENT'].append(-9)
                    # Assign other parameters
                    for kk, vv in v.items():
                        if kk not in KWS:
                            if kk not in self.data[module]:
                                self.data[module][kk] = []
                            self.data[module][kk].append(remove_quotes(vv))

    def __get_pipeline(self, module, module_id, module_idx, iteres):
        '''Input are last module name, ID, and its index (in its data frame)'''
        iteres.append((module, module_id))
        depend_id = self.data[module]['PARENT'][module_idx]
        if depend_id == -9:
            return
        else:
            idx = None
            module = None
            for k in self.data:
                # try get some idx
                try:
                    idx = self.data[k]['ID'].index(depend_id)
                    module = k
                    break
                except ValueError:
                    continue
            if idx is None or module is None:
                raise DBError('Cannot find module instance ID ``{}`` in any tables!'.format(depend_id))
            self.__get_pipeline(module, depend_id, idx, iteres)

    def write_master_table(self, module):
        '''
        Create a master table in DSCR flavor. Columns are:
        name, module1, module1_instance_ID, module2, module2_instance_ID, ...
        I'll create multiple master tables for as many as in self.end_modules.
        '''
        pipelines = []
        # A pipeline instance can be retrieved via:
        # (module -> depend_id -> id -> module ... )_n
        for module_idx, module_id in enumerate(self.data[module]['ID']):
            tmp = []
            self.__get_pipeline(module, module_id, module_idx, tmp)
            pipelines.append(tuple(reversed(tmp)))
        data = OrderedDict()
        for pipeline in pipelines:
            key = tuple(x[0] for x in pipeline)
            if key not in data:
                data[key] = [key]
            data[key].append([x[1] for x in pipeline])
        for key in list(data.keys()):
            header = data[key].pop(0)
            data[key] = pd.DataFrame(data[key], columns = header)
            data['+'.join(key)] = data.pop(key)
        return data

    def Build(self, script = None, groups = None):
        self.load_parameters()
        for module in self.end_modules:
            self.master[f'pipeline_{module}'] = self.write_master_table(module)
        output = dict()
        for module in self.data:
            cols = ['ID', 'PARENT', 'FILE'] + [x for x in self.data[module].keys() if x not in self.meta_kws]
            output[module] = self.data[module].pop('__out_vars__')
            self.data[module] = pd.DataFrame(self.data[module], columns = cols)
        self.data.update(self.master)
        if script is not None:
            self.data['.html'] = script
        if groups is not None:
            self.data['.groups'] = groups
        self.data['.output'] = output
        pickle.dump(self.data, open(self.prefix + '.db', 'wb'))

if __name__ == '__main__':
    import sys
    ResultDB(sys.argv[1], sys.argv[2]).Build('NULL')

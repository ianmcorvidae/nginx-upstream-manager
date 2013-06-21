#!/usr/bin/env python2
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from optparse import OptionParser
from os.path import dirname, exists
from os import remove

###########
# CLASSES #
###########

class Config:
    """A class encapsulating the config.yaml config file"""
    def __init__(self, filename=dirname(__file__) + '/config.yaml'):
        self.filename = filename
        self.config_raw = None
        self.config = None
        self.load()

    def load(self):
        if self.config_raw is None:
            self.load_raw()
        if self.config is None:
            self.process()

    def load_raw(self):
        config_file = open(self.filename)
        self.config_raw = load(config_file, Loader=Loader)
        config_file.close()

    def process(self):
        config_raw = self.config_raw

        config = dict([(cluster_key, dict([(server_key, config_raw.get('_default', {}).copy())
                                           for server_key in config_raw[cluster_key].keys()
                                           if server_key[0] != '_']))
                       for cluster_key in config_raw.keys()
                       if cluster_key[0] != '_'])
        for cluster_key in config.keys():
            for server_key in config[cluster_key].keys():
                config[cluster_key][server_key].update(config_raw[cluster_key].get('_default', {}))
                config[cluster_key][server_key].update(config_raw[cluster_key][server_key])

            config[cluster_key]['_ip_hash'] = bool(config_raw[cluster_key].get('_ip_hash', False))
            config[cluster_key]['_file'] = dirname(__file__) + '/' + config_raw[cluster_key].get('_file', cluster_key + '.conf')
        self.config = config

    def save(self):
        config_file = open(self.filename, 'w')
        config_file.write(dump(self.config_raw, default_flow_style=False, Dumper=Dumper))
        config_file.close()

    def cluster(self, cluster_name):
        return Cluster(cluster_name, self.config[cluster_name])

    def _set_prop(self, cluster, server, prop, value):
        cluster_name = cluster.name
        self.config[cluster_name][server][prop] = value

        cluster_default = self.config_raw[cluster_name].get('_default', {}).get(prop, None)
        global_default = self.config_raw.get('_default', {}).get(prop, None)
        if cluster_default == value or (cluster_default is None and global_default == value):
            if prop in self.config_raw[cluster_name][server]:
                del self.config_raw[cluster_name][server][prop]
        else:
            self.config_raw[cluster_name][server][prop] = value

    def enable(self, cluster, server):
        self._set_prop(cluster, server, 'enabled', 1)

    def disable(self, cluster, server):
        self._set_prop(cluster, server, 'enabled', 0)

    def backup(self, cluster, server):
        self._set_prop(cluster, server, 'backup', 1)

    def nonbackup(self, cluster, server):
        self._set_prop(cluster, server, 'backup', 0)

    def down(self, cluster, server):
        self._set_prop(cluster, server, 'down', 1)

    def up(self, cluster, server):
        self._set_prop(cluster, server, 'down', 0)

    def weight(self, cluster, server, new):
        if new is None:
            new = 1
        self._set_prop(cluster, server, 'weight', new)

    def max_fails(self, cluster, server, new):
        if new is None:
            new = 1
        self._set_prop(cluster, server, 'max_fails', new)

    def fail_timeout(self, cluster, server, new):
        if new is None:
            new = '10s'
        self._set_prop(cluster, server, 'fail_timeout', new)

class Cluster:
    """A class encapsulating a specific upstream/cluster"""
    def __init__(self, name, config):
        self.name = name
        self.ip_hash = config.get('_ip_hash')
        self.filename = config.get('_file')
        self.servers = [Server(name, config[name]) for name in config.keys() if name[0] != '_']

    def save(self, **kwargs):
        upstream_def = 'upstream %s {\n%%s}\n' % self.name
        if self.ip_hash:
            upstream_def = upstream_def % '    ip_hash;\n%s'
        count = 1
        for server in self.servers:
            if kwargs.get('rotate', False) == count:
                server.rotate = True
            upstream_def = upstream_def % server.comment_line('    ', '\n%s')
            upstream_def = upstream_def % server.upstream_line('    ', '\n%s')
            if server.active():
                count = count + 1
        upstream_def = upstream_def % ''

        config_file = open(self.filename, 'w')
        config_file.write(upstream_def)
        config_file.close()

class Server:
    """A class encapsulating a specific server within a cluster"""
    def __init__(self, name, config):
        self.name = name
        if config.get('host', False):
            self.host = config['host']
            self.port = config['port']
            self.upstream = "%s:%s" % (self.host, + self.port)
        elif config.get('upstream', False):
            self.host = self.port = None
            self.upstream = config['upstream']
        else:
            raise Exception('Please provide either host/port or upstream for server %s' % self.name)
        for prop in ['weight', 'max_fails', 'fail_timeout', 'down', 'backup', 'enabled']:
            setattr(self, prop, config.get(prop, None))
        self.rotate = False

    def active(self):
        return self.enabled and not self.down

    def comment_line(self, prefix='', postfix=''):
        ret = '# %s' % self.name
        if not self.enabled:
            ret = ret + ' (disabled)'
        if self.down:
            ret = ret + ' (down)'
        if self.rotate:
            ret = ret + ' (rotated out)'
        return prefix + ret + postfix

    def upstream_line(self, prefix='', postfix=''):
        properties = []
        if self.rotate:
            properties.append('#')
        elif not self.enabled:
            properties.append('##')

        properties.extend(['server', self.upstream])
        for prop in ['weight', 'max_fails', 'fail_timeout']:
            if getattr(self, prop) is not None:
                properties.append("%s=%s" % (prop, getattr(self, prop)))
        for prop in ['down', 'backup']:
            if getattr(self, prop):
                properties.append(prop)
        return prefix + " ".join(properties) + ';' + postfix

###########
# ACTIONS #
###########

def rotate_action(config, cluster, *other_args):
    statefile = dirname(__file__) + '/.rotate-' + cluster.name
    if exists(statefile):
        fh = open(statefile, 'r')
        state = int(fh.read().strip()) + 1
        fh.close()
    else:
        state = 1
    valid = [server.host for server in cluster.servers if server.active()]
    cluster.save(rotate=state)
    if state > len(valid):
        print "Done"
        remove(statefile)
    else:
        print valid[state - 1]
        fh = open(statefile, 'w')
        fh.write(str(state))
        fh.close()

def generate_action(config, cluster, *other_args):
    cluster.save()
    print "Saved"

def disable_action(config, cluster, args, options, parser):
    if len(args) < 1:
        parser.error('Please provide a server to disable.')
    to_disable = args[0]
    if cluster.ip_hash:
        config.down(cluster, to_disable)
    else:
        config.disable(cluster, to_disable)
    config.save()
    config.cluster(cluster.name).save()
    print "Disabled " + to_disable

def enable_action(config, cluster, args, options, parser):
    if len(args) < 1:
        parser.error('Please provide a server to enable.')
    to_enable = args[0]
    if cluster.ip_hash:
        config.enable(cluster, to_enable)
        config.up(cluster, to_enable)
    else:
        config.enable(cluster, to_enable)
    config.save()
    config.cluster(cluster.name).save()
    print "Enabled " + to_enable

def weight_action(config, cluster, args, options, parser):
    if len(args) < 1:
        parser.error('Please provide a server.')
    if len(args) < 2:
        parser.error('Please provide a new value.')
    server = args[0]
    value = args[1]
    config.weight(cluster, server, value)
    config.save()
    config.cluster(cluster.name).save()
    print "Changed %s weight to %s" % (server, value)

actions = {'generate': generate_action,
           'rotate': rotate_action,
           'disable': disable_action,
           'enable': enable_action,
           'weight': weight_action}

# Run the script!
if __name__ == '__main__':
    usage = """Usage: %%prog [options] cluster action [server ...]
           'cluster' should be a named cluster in your config file
           'action' should be one of: %s
           'server' and past is required for some action types""" % ", ".join(actions.keys())
    parser = OptionParser(usage=usage)
    (options, args) = parser.parse_args()

    if len(args) < 2:
        parser.error('Please provide both a cluster and an action!')

    config = Config()
    if args[0] not in config.config.keys():
        parser.error('Unknown cluster. Available clusters are: ' + ", ".join([k for k in config.config.keys() if k[0] != '_']))

    cluster = config.cluster(args[0])
    action = args[1]

    if action not in actions.keys():
        parser.error('Unknown action. Available actions are: ' + ", ".join(actions.keys()))

    actions[action](config, cluster, args[2:], options, parser)

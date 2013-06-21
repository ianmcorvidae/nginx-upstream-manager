This is a little script to manage nginx upstreams.

The intention is to put upstream_manager.py, plus a config.yaml, into a directory somewhere that you'd like nginx to look for upstream definitions to be included from other configuration files.

For example, you might create /etc/nginx/upstreams/ for these files. Then in your server configs, you can include them before you use the upstream definitions.

Given a configuration file, the script creates and manages the appropriate nginx configurations.

Invoke the script via:

    upstream_manager.py <cluster> <action> [...]

Available actions are:

* 'generate' which simply generates a file from the config for the provided cluster
* 'enable' and 'disable' which comment out a server or mark it as down, depending on whether or not you're using ip_hash. Requires another 'server' argument.
* 'weight' which changes the weight of a given server. Requires a server and a new value.
* 'rotate' which is designed for automated deployments; called subsequently, it will temporarily disable each of your upstream servers in order, printing out the IP of the server it disabled so you can hook into a deployment script. Once it's done all of them, it'll return 'Done' on the last invocation, and the next one will start another rotation.

See config.yaml.sample for a sample configuration, and fancycluster.conf.sample for the configuration that would generate.

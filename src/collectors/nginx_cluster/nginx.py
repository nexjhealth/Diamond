# coding=utf-8

"""
Collect statistics from Nginx

#### Dependencies

 * urllib2

#### Usage

To enable the nginx status page to work with defaults,
add a file to /etc/nginx/sites-enabled/ (on Ubuntu) with the
following content:
<pre>
  server {
      listen 127.0.0.1:8080;
      server_name localhost;
      location /nginx_status {
          stub_status on;
          access_log /data/server/shared/log/access.log;
          allow 127.0.0.1;
          deny all;
      }
  }
</pre>

"""

import urllib2
import re
import diamond.collector


class NginxNodeCollector(diamond.collector.Collector):

    def process_config(self):
        super(NginxNodeCollector, self).process_config()
        if 'url' in self.config:
            self.config['urls'].append(self.config['url'])

        self.urls = {}
        if isinstance(self.config['urls'], basestring):
            self.config['urls'] = self.config['urls'].split(',')

        for url in self.config['urls']:
            # Handle the case where there is a trailing comma in the urls list
            if len(url) == 0:
                continue
            if ' ' in url:
                parts = url.split(' ')
                self.urls[parts[0]] = parts[1]
            else:
                self.urls[''] = url

    def get_default_config_help(self):
        config_help = super(NginxNodeCollector, self).get_default_config_help()
        config_help.update({
            'urls': 'Nginx Nodes Enabled',
        })
        return config_help

    def get_default_config(self):
        config = super(NginxNodeCollector, self).get_default_config()
        config.update({
            'path': 'nginx',
            'urls': ['nginx1 http://127.0.0.1:8080/nginx_status']
        })
        return config

    def collect(self):
        for node in self.urls.keys():
            url = self.urls[node]

            activeConnectionsRE = re.compile(r'Active connections: (?P<conn>\d+)')
            totalConnectionsRE = re.compile('^\s+(?P<conn>\d+)\s+' +
                                            '(?P<acc>\d+)\s+(?P<req>\d+)')
            connectionStatusRE = re.compile('Reading: (?P<reading>\d+) ' +
                                            'Writing: (?P<writing>\d+) ' +
                                            'Waiting: (?P<waiting>\d+)')
            req = urllib2.Request(url=url, headers={})
            try:
                handle = urllib2.urlopen(req)
                for l in handle.readlines():
                    l = l.rstrip('\r\n')
                    if activeConnectionsRE.match(l):
                        self.publish_gauge(
                            'active_connections_%s' %node,
                            int(activeConnectionsRE.match(l).group('conn')))
                    elif totalConnectionsRE.match(l):
                        m = totalConnectionsRE.match(l)
                        req_per_conn = float(m.group('req')) / \
                            float(m.group('acc'))
                        self.publish_counter('conn_accepted_%s' %node, int(m.group('conn')))
                        self.publish_counter('conn_handled_%s' %node, int(m.group('acc')))
                        self.publish_counter('req_handled_%s' %node, int(m.group('req')))
                        self.publish_gauge('req_per_conn_%s' %node, float(req_per_conn))
                    elif connectionStatusRE.match(l):
                        m = connectionStatusRE.match(l)
                        self.publish_gauge('act_reads_%s' %node, int(m.group('reading')))
                        self.publish_gauge('act_writes_%s' %node, int(m.group('writing')))
                        self.publish_gauge('act_waits_%s' %node, int(m.group('waiting')))
            except IOError, e:
                self.log.error("Unable to open %s" % url)
            except Exception, e:
                self.log.error("Unknown error opening url: %s", e)

"""
Created on 4th March 2020

:author: Alan Greer
"""
import json
import logging
import os
from datetime import datetime
import time
import threading
from odin.adapters.adapter import ApiAdapter, ApiAdapterRequest, ApiAdapterResponse, request_types, response_types
from odin.adapters.parameter_tree import ParameterAccessor, ParameterTree, ParameterTreeError


SERVER_STATS_PROXY_ADAPTER_KEY = 'proxy_adapter'
SERVER_STATS_SERVERS_KEY = 'servers'
SERVER_STATS_POLL_RATE = 'update_rate'


class ServerStatsAdapter(ApiAdapter):
    """
    ServerStatsAdapter class

    Adapter that monitors multiple other odin server instances and
    scrapes the server statistics from adapters running on those 
    instances.
    The data is then flattened into a simple parameter tree that
    can be easily read by an EPICS client.
    """
    
    def __init__(self, **kwargs):
        """
        Initialise the ServerStatsAdapter object

        :param kwargs:
        """
        logging.info("ServerStatsAdapter init called")
        super(ApiAdapter, self).__init__()
        
        self._proxy_name = None
        if SERVER_STATS_PROXY_ADAPTER_KEY in kwargs:
            self._proxy_name = kwargs[SERVER_STATS_PROXY_ADAPTER_KEY]

        self._servers = []
        if SERVER_STATS_SERVERS_KEY in kwargs:
            server_ids = kwargs[SERVER_STATS_SERVERS_KEY].split(',')
            for server_id in server_ids:
                self._servers.append(server_id.strip())
            logging.info("Servers to be monitored:  {}".format(self._servers))

        self._stats_monitor = None

    def initialize(self, adapters):
        """Initialize the adapter after it has been loaded.
        For the stats adapter a proxy adapter is required to be able to 
        collect external server statistics.  The proxy adapter is searched
        for and recorded here for continued use
        """
        if self._proxy_name in adapters:
            self._proxy_adapter = adapters[self._proxy_name]
            logging.info("Initiated connection to proxy adapter: {}".format(self._proxy_name))
            self._stats_monitor = ServerStatistics(self._proxy_adapter, self._servers)
        else:
            logging.info("Failed to start server monitoring, no proxy adapter {} found".format(self._proxy_name))

    @request_types('application/json', 'application/vnd.odin-native')
    @response_types('application/json', default='application/json')
    def get(self, path, request):
        """
        Implementation of the HTTP GET verb for ServerStatsAdapter

        :param path: URI path of the GET request
        :param request: Tornado HTTP request object
        :return: ApiAdapterResponse object to be returned to the client
        """
        status_code = 200
        response = {}
        try:
            response = self._stats_monitor.get(path)
        except ParameterTreeError as ex:
            # Set the status code to error
            status_code = 404
            response['error'] = str(ex)
        return ApiAdapterResponse(response, status_code=status_code)

    @request_types('application/json', 'application/vnd.odin-native')
    @response_types('application/json', default='application/json')
    def put(self, path, request):  # pylint: disable=W0613
        """
        Implementation of the HTTP PUT verb for SeverStatsAdapter

        This adapter is readonly and will always return an error 400        

        :param path: URI path of the PUT request
        :param request: Tornado HTTP request object
        :return: ApiAdapterResponse object to be returned to the client
        """
        status_code = 400
        response = {'error': 'ServerStatsAdapter is read only'}

        return ApiAdapterResponse(response, status_code=status_code)

    def cleanup(self):
        logging.info("Cleanup called for server_stats_adapter.py")
        if self._stats_monitor is not None:
            self._stats_monitor.shutdown()


class ServerStatistics(object):
    """
    ServerStatistics class

    This class creates a simple parameter tree structure and then
    monitors an arbitrary quantity of external odin control servers
    that are running the statistics adapters.

    This class collects data from each of those instances and places
    it into the parameter tree for easy access by a client.
    """

    SERVER_TREE = {
        'name': '',
        'disk': {
            'name': '',
            'percent': 0.0,
            'free': 0
        },
        'net': {
            'name': '',
            'pkts': {
                'sent': 0,
                'recv': 0
            },
            'dropin': 0,
            'errin': 0
        }
    }

    def __init__(self, proxy, servers, update_rate=1.0):
        """
        Constructor, builds the tree from the sever list

        :param proxy: The proxy adapter required by this adapter to be
        able to communicate with external odin control server instances
        :param servers: The list of servers that are to be monitored
        :param update_rate: The rate at which the servers should be monitored
        """
        self._running = True

        # From the arguments we need to extract
        # the proxy adapter
        self._proxy = proxy

        # Store the list of servers that provide the information
        self._servers = {}

        # Servers will be stored as sv<n> where <n> is a zero based index

        # For each server we have the following Tree
        # name: string
        # disk/name: string
        # disk/percent: float
        # disk/free: int
        # net/name: string
        # net/pkts/sent: int
        # net/pkts/recv: int
        # net/dropin: int
        # net/errin: int
        param_tree = {'status': {}}
        server_index = 0
        for server in servers:
            server_param_name = 'sv{}'.format(server_index)
            self._servers[server] = server_param_name
            param_tree['status'][server_param_name] = self.create_param_structure(server_param_name + '_', self.SERVER_TREE)
            setattr(self, server_param_name + '_name', server)
            server_index += 1

        # Create the parameter tree from the dictionary of values
        self._param_tree = ParameterTree(param_tree)

        # Set the polling update rate
        self._update_delay = update_rate

        # Start the status thread
        self._status_thread = threading.Thread(target=self.status_loop)
        self._status_thread.start()

    def get(self, path):
        """
        returns a value (or complex structure from the parameter tree)

        :param path: path to the value to return
        :return dict: The value or complex tree to return
        """
        param = path.split('/')[-1]
        response = self._param_tree.get(path, True)[param]
        return response

    def create_param_structure(self, path, tree):
        """
        Creates a parameter structure and sets up the corresponding local
        member attributes to store the underlying values.

        This method is recursive

        :param path: path to this level of the tree
        :param tree: the tree structure to traverse and setup variables for
        :return dict: The full tree description ready to be passed into a parameter tree
        """
        reply = {}
        for param_name in tree:
            full_name = path + param_name
            if isinstance(tree[param_name], dict):
                reply[param_name] = self.create_param_structure(full_name + '_', tree[param_name])
            else:
                logging.info("Creating attribute: {}".format(full_name))
                setattr(self, full_name, tree[param_name])
                reply[param_name] = (lambda x=full_name: getattr(self, x), {})
        return reply

    def shutdown(self):
        """
        Shuts down the monitoring thread
        """
        self._running = False

    def status_loop(self):
        """
        Monitors the external servers and fills in the local attributes with updated values
        """
        while self._running:
            # Check we have a proxy adapter available
            if self._proxy is not None:
                # Call GET to obtain the list of all proxies
                req = ApiAdapterRequest(None, accept='application/json')
                for server in self._servers:
                    try:
                        server_name = self._servers[server]
                        status_dict = self._proxy.get(path=server, request=req).data
                        # Now we need to create and match parameters
                        disk_tree = status_dict[server]['status']['disk']
                        for disk_name in disk_tree:
                            full_name = server_name + '_disk_name'
                            setattr(self, full_name, disk_name.replace('_', '/'))
                            full_name = server_name + '_disk_percent'
                            setattr(self, full_name, disk_tree[disk_name]['percent'])
                            full_name = server_name + '_disk_free'
                            setattr(self, full_name, disk_tree[disk_name]['free']/(1024*1024))
                        network_tree = status_dict[server]['status']['network']
                        for network_name in network_tree:
                            full_name = server_name + '_net_name'
                            setattr(self, full_name, network_name)
                            full_name = server_name + '_net_pkts_sent'
                            setattr(self, full_name, network_tree[network_name]['packets_sent'])
                            full_name = server_name + '_net_pkts_recv'
                            setattr(self, full_name, network_tree[network_name]['packets_recv'])
                            full_name = server_name + '_net_dropin'
                            setattr(self, full_name, network_tree[network_name]['dropin'])
                            full_name = server_name + '_net_errin'
                            setattr(self, full_name, network_tree[network_name]['errin'])
                    except:
                        logging.error("Failed to get statistics from {}".format(server))
            
            time.sleep(self._update_delay)

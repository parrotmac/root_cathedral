from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc import udp_client

from enum import Enum
from time import sleep
from threading import Thread
import json


class WalabotOSC:
    """
        MQTT client which publishes walabots data.
        import to WalabotHandler is reburied.
    """
    class Status(Enum):
        PENDING = 0
        WORKING = 1

    def __init__(self, walabotHandler):
        print("Initializing")
        self.__walabot = walabotHandler()
        self.__status = self.Status.PENDING
        self.__working_thread = 0
        
        if self.__walabot.out_ip is not None and self.__walabot.out_port is not None:
            print("Starting client at {}:{}".format(self.__walabot.out_ip, self.__walabot.out_port))
            self.__osc_client = udp_client.SimpleUDPClient(self.__walabot.out_ip, int(self.__walabot.out_port))
        else:
            print('no OUT ip or port specified')

        if self.__walabot.in_ip is not None and self.__walabot.in_port is not None:
            print("Starting server at {}:{}".format(self.__walabot.in_ip, self.__walabot.in_port))
            self.__dispatcher = dispatcher.Dispatcher()
            self.__dispatcher.map("/stop", self.__on_stop)
            self.__dispatcher.map("/start", self.__on_start)
            self.__dispatcher.map("/disconnect", self.__on_disconnect)

            self.__osc_server = osc_server.ThreadingOSCUDPServer(
            (self.__walabot.in_ip, int(self.__walabot.in_port)), self.__dispatcher)
            self.__osc_server.serve_forever()
        else: 
            print('no IN ip or port specified')

    def __on_stop(self, address, *args):
        print("Stopped")
        self.__status = self.Status.PENDING
        self.__working_thread.join(timeout=2)

    def __on_start(self, address, *args):
        print("Started")
        if self.__status == self.Status.WORKING:
            return False
        self.__status = self.Status.WORKING
        self.__working_thread = Thread(target=self.__data_loop)
        self.__working_thread.start()    

    def __on_disconnect(self, address, *args):
        if self.__status is self.Status.WORKING:
            self.__status = self.Status.PENDING
            self.__working_thread.join(timeout=2)
            self.__osc_server.disconnect()

    def __data_loop(self):
        is_connected = self.__walabot.start()
        if self.__walabot.device_name is None:
            self.__osc_client.send_message("/walabot/error", -2)
            self.__status = self.Status.PENDING             
        elif not is_connected:
            self.__osc_client.send_message("/walabot/{}/error".format( self.__walabot.device_name), -1)
            self.__status = self.Status.PENDING       
        else:
            self.__osc_client.send_message("/walabot/{}/start".format( self.__walabot.device_name), 0)
        error_counter = 0
        while self.__status is self.Status.WORKING:
            data = dict()
            rc = self.__walabot.get_data(data)
            if rc:
                for key, value in data.items():
                    self.__osc_client.send_message("/walabot/{}/{}".format( self.__walabot.device_name, key), value)
                error_counter = 0
            else:
                error_counter += 1
                if error_counter >= 100:
                    self.__osc_client.send_message("/walabot/{}/error".format( self.__walabot.device_name), error_counter)
                    self.__status = self.Status.PENDING
            sleep(0.03)
        self.__walabot.stop()
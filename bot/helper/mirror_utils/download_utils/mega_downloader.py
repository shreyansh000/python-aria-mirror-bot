from bot import LOGGER, MEGA_API_KEY, download_dict_lock, download_dict, MEGA_EMAIL_ID, MEGA_PASSWORD
import threading
# from mega import (MegaApi, MegaListener, MegaRequest, MegaTransfer, MegaError)
from bot.helper.telegram_helper.message_utils import update_all_messages
import os
from bot.helper.mirror_utils.status_utils.mega_download_status import MegaDownloadStatus
import random
import string

class MegaDownloaderException(Exception):
    pass


class MegaAppListener(MegaListener):
    _NO_EVENT_ON = (MegaRequest.TYPE_LOGIN,
                    MegaRequest.TYPE_FETCH_NODES)

    def __init__(self, continue_event: threading.Event, listener):
        self.continue_event = continue_event
        self.node = None
        self.listener = listener
        self.uid = listener.uid
        self.__bytes_transferred = 0
        self.is_cancelled = False
        self.__speed = 0
        self.__name = ''
        self.__size = 0
        self.error = None
        self.gid = ""
        super(MegaAppListener, self).__init__()

    @property
    def speed(self):
        """Returns speed of the download in bytes/second"""
        return self.__speed

    @property
    def name(self):
        """Returns name of the download"""
        return self.__name

    def setValues(self, name, size, gid):
        self.__name = name
        self.__size = size
        self.gid = gid

    @property
    def size(self):
        """Size of download in bytes"""
        return self.__size

    @property
    def downloaded_bytes(self):
        return self.__bytes_transferred

    def onRequestStart(self, api, request):
        LOGGER.info('Request start ({})'.format(request))

    def onRequestFinish(self, api, request, error):
        LOGGER.info('Mega Request finished ({}); Result: {}'
                    .format(request, error))

        request_type = request.getType()
        if request_type == MegaRequest.TYPE_LOGIN:
            api.fetchNodes()
        elif request_type == MegaRequest.TYPE_GET_PUBLIC_NODE:
            self.node = request.getPublicMegaNode()
        elif request_type == MegaRequest.TYPE_FETCH_NODES:
            LOGGER.info("Fetching Root Node.")
            self.node = api.getRootNode()
        if request_type not in self._NO_EVENT_ON:
            self.continue_event.set()

    def onRequestTemporaryError(self, api, request, error: MegaError):
        self.listener.onDownloadError(error.toString())
        self.error = error.toString()
        self.continue_event.set()

    def onTransferStart(self, api: MegaApi, transfer: MegaTransfer):
        LOGGER.info(f"Transfer Started: {transfer.getFileName()}")

    def onTransferUpdate(self, api: MegaApi, transfer: MegaTransfer):
        if self.is_cancelled:
            api.cancelTransfer(transfer, None)
        self.__speed = transfer.getSpeed()
        self.__bytes_transferred = transfer.getTransferredBytes()

    def onTransferFinish(self, api: MegaApi, transfer: MegaTransfer, error):
        try:
            LOGGER.info(f'Transfer finished ({transfer}); Result: {transfer.getFileName()}')
            if str(error) != "No error" and self.is_cancelled:
                self.is_cancelled = False
                return self.listener.onDownloadError(error.toString())
            if transfer.isFolderTransfer() and transfer.isFinished() and not self.is_cancelled or transfer.getFileName() == self.name and not self.is_cancelled:
                self.listener.onDownloadComplete()
        except Exception as e:
            LOGGER.error(e)

    def onTransferTemporaryError(self, api, transfer, error):
        LOGGER.info(f'Mega download error in file {transfer} {transfer.getFileName()}: {error}')
        self.listener.onDownloadError(error.toString())
        self.error = error.toString()
        self.continue_event.set()

    def cancel_download(self):
        self.is_cancelled = True


class AsyncExecutor:

    def __init__(self):
        self.continue_event = threading.Event()

    def do(self, function, args):
        self.continue_event.clear()
        function(*args)
        self.continue_event.wait()

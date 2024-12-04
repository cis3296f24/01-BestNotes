import asyncio
import uuid
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, Any, Dict, List

# Enums for signaling and ICE connection states
class RTCSignalingState(Enum):
    STABLE = "stable"
    HAVE_LOCAL_OFFER = "have-local-offer"
    HAVE_REMOTE_OFFER = "have-remote-offer"
    HAVE_LOCAL_PRANSWER = "have-local-pranswer"
    HAVE_REMOTE_PRANSWER = "have-remote-pranswer"
    CLOSED = "closed"

class RTCIceConnectionState(Enum):
    NEW = "new"
    CHECKING = "checking"
    CONNECTED = "connected"
    COMPLETED = "completed"
    FAILED = "failed"
    DISCONNECTED = "disconnected"
    CLOSED = "closed"

# Data classes for SDP and ICE candidates
@dataclass
class RTCIceCandidate:
    candidate: str
    sdpMid: str
    sdpMLineIndex: int

@dataclass
class RTCSessionDescription:
    type: str
    sdp: str

# DataChannel class
class DataChannel:
    def __init__(self, label: str, id: Optional[int] = None):
        self.label = label
        self.id = id or uuid.uuid4().int % 65535  # Random ID if none provided
        self.onmessage: Optional[Callable[[Any], None]] = None
        self.onopen: Optional[Callable[[], None]] = None
        self.onclose: Optional[Callable[[], None]] = None
        self.readyState = "connecting"
        self._peer_channel: Optional['DataChannel'] = None

    async def send(self, data: Any):
        if self.readyState != "open":
            raise RuntimeError("Data channel is not open")
        if self._peer_channel and self._peer_channel.onmessage:
            await asyncio.sleep(0.05)  # Simulated delay
            self._peer_channel.onmessage(data)

    def close(self):
        self.readyState = "closed"
        if self.onclose:
            asyncio.create_task(self._trigger_callback(self.onclose))

    async def _trigger_callback(self, callback: Callable):
        try:
            await asyncio.get_event_loop().run_in_executor(None, callback)
        except Exception as e:
            print(f"Error in DataChannel callback: {e}")

# WebRTCConnection class
class WebRTCConnection:
    def __init__(self, ice_servers: List[Dict[str, Any]]):
        self.ice_servers = ice_servers
        self.signalingState = RTCSignalingState.STABLE
        self.iceConnectionState = RTCIceConnectionState.NEW

        self.onicecandidate: Optional[Callable[[RTCIceCandidate], None]] = None
        self.ondatachannel: Optional[Callable[[DataChannel], None]] = None
        self.oniceconnectionstatechange: Optional[Callable[[], None]] = None

        self.localDescription: Optional[RTCSessionDescription] = None
        self.remoteDescription: Optional[RTCSessionDescription] = None
        self._data_channels: Dict[int, DataChannel] = {}
        self._ice_candidates: List[RTCIceCandidate] = []

    def add_ice_server(self, server: Dict[str, Any]):
        """Add an ICE server dynamically."""
        self.ice_servers.append(server)
        print(f"Added ICE server: {server}")

    async def create_offer(self) -> RTCSessionDescription:
        if self.signalingState != RTCSignalingState.STABLE:
            raise RuntimeError("Invalid signaling state to create offer")
        sdp = self._create_base_sdp()
        offer = RTCSessionDescription(type="offer", sdp=sdp)
        await self.set_local_description(offer)
        return offer

    async def create_answer(self) -> RTCSessionDescription:
        if self.signalingState != RTCSignalingState.HAVE_REMOTE_OFFER:
            raise RuntimeError("Invalid signaling state to create answer")
        sdp = self._create_base_sdp()
        answer = RTCSessionDescription(type="answer", sdp=sdp)
        await self.set_local_description(answer)
        return answer

    async def set_local_description(self, description: RTCSessionDescription):
        self.localDescription = description
        if description.type == "offer":
            self.signalingState = RTCSignalingState.HAVE_LOCAL_OFFER
        elif description.type == "answer":
            self.signalingState = RTCSignalingState.STABLE
            await self._complete_connection()

    async def set_remote_description(self, description: RTCSessionDescription):
        self.remoteDescription = description
        if description.type == "offer":
            self.signalingState = RTCSignalingState.HAVE_REMOTE_OFFER
        elif description.type == "answer":
            self.signalingState = RTCSignalingState.STABLE
            await self._complete_connection()

    def add_ice_candidate(self, candidate: RTCIceCandidate):
        self._ice_candidates.append(candidate)
        print(f"Added ICE Candidate: {candidate}")
        asyncio.create_task(self._process_ice_candidates())

    async def _process_ice_candidates(self):
        for candidate in self._ice_candidates:
            print(f"Processing ICE Candidate: {candidate}")
        self._ice_candidates.clear()

    def create_data_channel(self, label: str) -> DataChannel:
        channel = DataChannel(label)
        self._data_channels[channel.id] = channel
        asyncio.create_task(self._establish_channel(channel))
        return channel

    async def _establish_channel(self, channel: DataChannel):
        await asyncio.sleep(0.1)  # Simulated delay
        channel.readyState = "open"
        if channel.onopen:
            await channel._trigger_callback(channel.onopen)

    async def _complete_connection(self):
        if (self.localDescription and self.remoteDescription and
                self.signalingState == RTCSignalingState.STABLE):
            print("Connection established!")
            self.iceConnectionState = RTCIceConnectionState.CONNECTED

    def _create_base_sdp(self) -> str:
        sdp = [
            "v=0\r\n",
            "o=- 0 0 IN IP4 127.0.0.1\r\n",
            "s=-\r\n",
            "t=0 0\r\n",
            "a=group:BUNDLE data\r\n",
            "m=application 9 UDP/DTLS/SCTP webrtc-datachannel\r\n",
            "c=IN IP4 0.0.0.0\r\n",
            "a=setup:actpass\r\n",
            "a=sctp-port:5000\r\n"
        ]

        # Add ICE servers
        for server in self.ice_servers:
            if 'urls' in server:
                if server['urls'].startswith('turn:'):
                    sdp.append(f"a=ice-server:{server['urls']}")
                    if 'username' in server and 'credential' in server:
                        sdp.append(f"a=ice-ufrag:{server['username']}\r\n")
                        sdp.append(f"a=ice-pwd:{server['credential']}\r\n")

        return "".join(sdp)

    def close(self):
        self.signalingState = RTCSignalingState.CLOSED
        self.iceConnectionState = RTCIceConnectionState.CLOSED
        for channel in self._data_channels.values():
            channel.close()
        self._data_channels.clear()
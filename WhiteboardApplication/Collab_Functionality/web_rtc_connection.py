class WebRTCConnection:
    def __init__(self, ice_servers):
        """Initialize a WebRTC connection."""
        self.ice_servers = ice_servers
        self.ice_candidates = []  # To store ICE candidates
        self.data_channels = []   # To store data channels
        self.sdp_offer = None
        self.sdp_answer = None
        print("WebRTC connection initialized with ICE servers:", ice_servers)

    def on_ice_candidate(self, candidate):
        """Simulate the process of gathering ICE candidates."""
        print(f"New ICE candidate: {candidate}")
        self.ice_candidates.append(candidate)
        # Normally you would send the candidate to the peer via signaling

    def create_data_channel(self, label):
        """Simulate the creation of a data channel."""
        data_channel = DataChannel(label)
        self.data_channels.append(data_channel)
        print(f"Data channel created: {label}")
        return data_channel

    def set_local_sdp(self, sdp):
        """Simulate setting the local SDP offer/answer."""
        self.sdp_offer = sdp
        print("Local SDP set:", sdp)

    def set_remote_sdp(self, sdp):
        """Simulate setting the remote SDP offer/answer."""
        self.sdp_answer = sdp
        print("Remote SDP set:", sdp)

    def close(self):
        """Close the WebRTC connection."""
        print("Closing WebRTC connection.")
        self.ice_candidates.clear()
        self.data_channels.clear()

class DataChannel:
    def __init__(self, label):
        """Simulate a data channel."""
        self.label = label
        self.onmessage = None  # Set a callback for incoming messages
        print(f"Data channel created: {label}")

    def send(self, message):
        """Simulate sending a message over the data channel."""
        print(f"Sending message on channel {self.label}: {message}")
        if self.onmessage:
            self.onmessage(message)
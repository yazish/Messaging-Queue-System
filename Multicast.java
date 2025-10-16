import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.NetworkInterface;
import java.net.SocketException;
import java.net.StandardSocketOptions;
import java.nio.channels.DatagramChannel;
import java.util.Enumeration;

public class Multicast {
    /**
     * Gets an interface suitable for listening to multicast messages on.
     * 
     * Naively pick the first non-loopback interface capable of multicast. This should be fine on
     * aviary machines, as they only have a single interface configured, but may not work properly
     * on machines with multiple interfaces.
     * 
     * @return an interface suitable for listening to multicast messages on.
     */
    private static NetworkInterface getListeningInterface() {
        NetworkInterface target = null;
        try {
            Enumeration<NetworkInterface> ifs = NetworkInterface.getNetworkInterfaces();
            while (ifs.hasMoreElements() && target == null) {
                NetworkInterface next = ifs.nextElement();
                if (!next.isLoopback() && next.supportsMulticast()) {
                    target = next;
                }
            }
        } catch (SocketException e) {
            System.out.println("Error determining listening interface: " + e.getMessage());   
        }
        return target;
    }
    
    /**
     * Creates a DatagramChannel configured to send multicast messages.
     * 
     * Send messages to the appropriate address and port, just like you would a normal 
     * DatagramChannel. Channel is blocking by default.
     * 
     * @return a channel configured to send multicast messages.
     * @throws IOException if there is an error when creating the channel.
     */
    static DatagramChannel multicastSenderChannel() throws IOException {
        DatagramChannel channel = DatagramChannel.open()
            .setOption(StandardSocketOptions.SO_REUSEADDR, true)
            .setOption(StandardSocketOptions.IP_MULTICAST_TTL, 32);

        return channel;
    }

    /**
     * Creates a DatagramChannel configured to listen to multicast messages for a given group.
     * 
     * Receive messages using the normal `.read(buff)` method. Channel is blocking by default.
     * 
     * @param grpAddr the address of the multicast group.
     * @param grpPort the port of the multicast group.
     * @return a channel configured to receive messages for the given multicast group.
     * @throws IOException
     */
    static DatagramChannel multicastReceiverChannel(String grpAddr, int grpPort) 
            throws IOException {
        DatagramChannel channel = DatagramChannel.open()
                .setOption(StandardSocketOptions.SO_REUSEADDR, true)
                .bind(new InetSocketAddress(grpPort));
        
        channel.join(InetAddress.getByName(grpAddr), getListeningInterface());

        return channel;
    }
}

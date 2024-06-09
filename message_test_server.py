import socket


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 1337))

    while True:
        data, address = sock.recvfrom(1024)
        print(f"recv {address}: {data.decode()}")

        msg = f"hello, {address[0]}, you said: {data.decode()}"
        sock.sendto(msg.encode(), address)


if __name__ == "__main__":
    main()

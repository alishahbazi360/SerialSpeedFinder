import serial
import time
import ctypes

PORT = "COM8"

# BAUD_RATES = [
#     75, 110, 134, 150, 300, 600, 1200, 1800,
#     2400, 4800, 7200, 9600, 14400, 19200,
#     28800, 38400, 56000, 57600, 115200,
#     128000, 153600, 230400, 256000, 460800,
#     500000, 576000, 921600, 1000000, 1152000,
#     1500000, 2000000, 2500000, 3000000, 3500000,
#     4000000
# ]
BAUD_RATES = [
    9600,19200,38400,57600,115200
]


def hard_reset_port(port):
    """
    Fully reset a COM port using Win32 API.
    """
    GENERIC_READ  = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    FILE_FLAG_OVERLAPPED = 0x40000000

    # Open low-level handle
    handle = ctypes.windll.kernel32.CreateFileW(
        fr"\\.\{port}",
        GENERIC_READ | GENERIC_WRITE,
        0,
        None,
        OPEN_EXISTING,
        FILE_FLAG_OVERLAPPED,
        None
    )

    if handle == -1:
        return False

    # Purge RX/TX buffers
    PURGE_RXCLEAR = 0x0008
    PURGE_TXCLEAR = 0x0004
    ctypes.windll.kernel32.PurgeComm(handle, PURGE_RXCLEAR | PURGE_TXCLEAR)

    # Close handle
    ctypes.windll.kernel32.CloseHandle(handle)

    time.sleep(0.2)
    return True

# --- Force-close COM port using Windows API ---
def force_close_port(port):
    handle = ctypes.windll.kernel32.CreateFileW(
        fr"\\.\{port}",
        0xC0000000,  # GENERIC_READ | GENERIC_WRITE
        0,
        None,
        3,          # OPEN_EXISTING
        0,
        None
    )
    if handle != -1:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False

# --- Deep CH340 reset using DTR/RTS toggling ---
def reset_ch340(port):
    try:
        ser = serial.Serial(port=port, baudrate=9600, timeout=1)
        ser.dtr = False
        ser.rts = False
        time.sleep(0.1)
        ser.dtr = True
        ser.rts = True
        time.sleep(0.1)
        ser.close()
        return True
    except:
        return False

# --- Send Enter and read up to 20048 bytes ---
def send_enter_and_read(ser, wait_time=1.0):
    try:
        time.sleep(wait_time)  # give device time to wake up
        ser.write(b"\r\r")
       # Send Enter key
        time.sleep(wait_time)  # wait for response
        data = ser.read(90048)
        return data
    except Exception as e:
        print(f"Error while sending Enter: {e}")
        return b""

# --- Try opening the port at a given baud ---
def try_open(port, baud):
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = 1

    try:
        ser.open()
        print(f"✔ Opened {port} at {baud}")

        response = send_enter_and_read(ser)
        ser.close()
        return True, response, ser

    except Exception as e:
        print(f"❌ Failed at {baud}: {e}")
        return False, b"", ser

    finally:
        if ser.is_open:
            ser.close()


def user_confirms_output(data, baud):
    """
    Show the output to the user and ask if it's correct.
    """
    print("\n=== Output detected at baud", baud, "===")
    print(data)
    print("====================================")

    ans = input("Is this correct output? (y/n): ").strip().lower()
    return ans == "y"


def is_garbage(data):
    """
    Reject responses that contain NO printable ASCII characters.
    Accept only if at least one printable ASCII exists.
    """
    if not data:
        return True

    # Printable ASCII range: 0x20–0x7E
    for b in data:
        if 0x20 <= b <= 0x7E:
            return False  # has printable ASCII → NOT garbage

    return True  # no printable ASCII → garbage





# --- Main scanner ---
def scan(port):
    last_ser = None
    print(f"\n=== Scanning {port} ===\n")

    for baud in BAUD_RATES:
        print(f"Trying {baud} baud...")

        # -------------------------
        # Attempt 1
        # -------------------------
        ok, data, ser = try_open(port, baud)
        last_ser = ser

        if ok and data and not is_garbage(data):
            if user_confirms_output(data, baud):
                print(f"\n🎉 User confirmed baud rate {baud}!")
                if last_ser and last_ser.is_open:
                    print("Closing serial port...")
                    last_ser.close()
                return baud
            else:
                print("User rejected output, continuing...\n")
        else:
            print("Auto-rejected garbage output.\n")

        # -------------------------
        # Attempt 2 — HARD RESET + CH340 RESET
        # -------------------------
        print(f"⚠ Hard-resetting {port} and retrying {baud}...")
        hard_reset_port(port)
        reset_ch340(port)
        time.sleep(0.3)

        ok2, data2, ser2 = try_open(port, baud)
        last_ser = ser2

        if ok2 and data2 and not is_garbage(data2):
            if user_confirms_output(data2, baud):
                print(f"\n🎉 User confirmed baud rate {baud}!")
                if last_ser and last_ser.is_open:
                    print("Closing serial port...")
                    last_ser.close()
                return baud
            else:
                print("User rejected output, continuing...\n")
        else:
            print("Auto-rejected garbage output.\n")

        # -------------------------
        # Attempt 3 — HARD RESET + CH340 RESET AGAIN
        # -------------------------
        print(f"⚠ Hard-resetting {port} and retrying {baud} (final attempt)...")
        hard_reset_port(port)
        reset_ch340(port)
        time.sleep(0.3)

        ok3, data3, ser3 = try_open(port, baud)
        last_ser = ser3

        if ok3 and data3 and not is_garbage(data3):
            if user_confirms_output(data3, baud):
                print(f"\n🎉 User confirmed baud rate {baud}!")
                if last_ser and last_ser.is_open:
                    print("Closing serial port...")
                    last_ser.close()
                return baud
            else:
                print("User rejected output, continuing...\n")
        else:
            print("Auto-rejected garbage output.\n")

        print(f"❌ Baud {baud} failed three times, moving on.")

    # -------------------------
    # End of scan — close port
    # -------------------------
    if last_ser and last_ser.is_open:
        print("Closing serial port...")
        last_ser.close()

    print("\n❌ No working baud rate found.")
    return None



if __name__ == "__main__":
    scan(PORT)

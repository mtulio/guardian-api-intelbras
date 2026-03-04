import asyncio
from app.services.isecnet_protocol import ISECNetProtocol

async def test():
    proto = ISECNetProtocol()
    reader, writer = await asyncio.open_connection('192.168.1.5', 9009)
    proto.reader = reader
    proto.writer = writer
    proto.is_connected = True
    
    print("Sending V2 Auth directly without handshake...")
    cmd = proto._build_auth_cmd("123456", is_ip_receiver=True)
    writer.write(cmd)
    
    try:
        resp = await asyncio.wait_for(reader.read(1024), timeout=3)
        print("V2 Auth Response:", resp.hex())
    except:
        print("No V2 Auth response")
        
    print("\nSending V1 Status directly...")
    cmd_v1 = proto._build_isecv1_status_cmd("1234")
    writer.write(cmd_v1)
    try:
        resp_v1 = await asyncio.wait_for(reader.read(1024), timeout=3)
        print("V1 Status Response:", resp_v1.hex())
    except:
        print("No V1 Status response")

asyncio.run(test())

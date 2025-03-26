import asyncio

from grpclib.client import Channel

from device_gateway.gen.qpu_interface.v1 import GetDeviceInfoRequest, QpuServiceStub


async def main():
    channel = Channel(host="localhost", port=50051)
    service = QpuServiceStub(channel)

    try:
        response = await service.get_device_info(GetDeviceInfoRequest())
        print("Response:", response)
    except Exception as e:
        print("Error:", e)
    finally:
        channel.close()


if __name__ == "__main__":
    asyncio.run(main())

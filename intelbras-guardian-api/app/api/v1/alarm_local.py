from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from app.api.v1.alarm import ArmMode, AlarmOperationResponse, AlarmStatusResponse, PartitionStatusInfo, ZoneStatusInfo
from app.services.isecnet_client import isecnet_client
from app.core.exceptions import APIConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alarm/local", tags=["Local Alarm Control"])

class LocalConnectionRequest(BaseModel):
    """Base model for local connection requests."""
    local_ip: str = Field(..., description="Local IP address of the alarm panel")
    local_port: int = Field(default=9009, description="Local port of the alarm panel (usually 9009 or 9015)")
    mac: Optional[str] = Field(None, description="MAC address of the alarm panel, used as the account for IP Receiver")
    password: str = Field(..., min_length=4, max_length=6, description="Alarm panel password (4-6 digits)")


class LocalArmRequest(LocalConnectionRequest):
    """Local arm request model."""
    partition_id: Optional[int] = Field(None, description="Partition index to arm (None = all partitions, 0-based)")
    mode: ArmMode = Field(default=ArmMode.AWAY, description="Arm mode: away (total) or home (stay)")


class LocalDisarmRequest(LocalConnectionRequest):
    """Local disarm request model."""
    partition_id: Optional[int] = Field(None, description="Partition index to disarm (None = all partitions, 0-based)")


@router.post("/status", response_model=AlarmStatusResponse)
async def get_local_alarm_status(request: LocalConnectionRequest):
    """
    Get current alarm status directly using local IP Receiver protocol.
    Bypasses Intelbras Cloud API completely.
    """
    try:
        logger.info(f"Getting local status for device with MAC: {request.mac} at {request.local_ip}:{request.local_port}")

        # device_id is 0 for local as there is no cloud DB ID
        device_id = 0
        mac_to_use = request.mac or ""
        success, status, message = await isecnet_client.get_status(
            device_id=device_id,
            mac=mac_to_use,
            password=request.password,
            use_ip_receiver=True,
            ip_receiver_addr=request.local_ip,
            ip_receiver_port=request.local_port,
            ip_receiver_account=request.mac
        )

        if not success:
            raise APIConnectionError(f"Failed to get local status: {message}")

        partitions = [
            PartitionStatusInfo(index=p["index"], state=p["state"])
            for p in status.partitions
        ]

        zones = [
            ZoneStatusInfo(
                index=z["index"],
                name=f"Zona {z['index'] + 1:02d}",
                is_open=z.get("open", False),
                is_bypassed=z.get("bypassed", False),
                is_wireless=z.get("is_wireless", False),
                battery_low=z.get("battery_low", False),
                signal_strength=z.get("signal_strength"),
                tamper=z.get("tamper", False)
            )
            for z in status.zones
        ]

        return AlarmStatusResponse(
            device_id=device_id,
            model=status.model,
            mac=status.mac or request.mac,
            is_armed=status.is_armed,
            arm_mode=status.arm_mode,
            is_triggered=status.is_triggered,
            partitions=partitions,
            partitions_enabled=status.partitions_enabled,
            zones=zones,
            message=message,
            is_eletrificador=status.is_eletrificador,
            shock_enabled=status.shock_enabled,
            shock_triggered=status.shock_triggered,
            alarm_enabled=status.alarm_enabled,
            alarm_triggered=status.alarm_triggered
        )

    except APIConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e.message))
    except Exception as e:
        logger.error(f"Unexpected error getting local status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/arm", response_model=AlarmOperationResponse)
async def arm_local_partition(request: LocalArmRequest):
    """
    Arm a partition directly using local IP Receiver protocol.
    Bypasses Intelbras Cloud API completely.
    """
    try:
        logger.info(f"Arming locally MAC: {request.mac} at {request.local_ip}:{request.local_port} partition_index={request.partition_id} mode={request.mode}")

        device_id = 0
        mac_to_use = request.mac or ""
        success, message = await isecnet_client.arm(
            device_id=device_id,
            mac=mac_to_use,
            password=request.password,
            mode=request.mode.value,
            partition_index=request.partition_id,
            use_ip_receiver=True,
            ip_receiver_addr=request.local_ip,
            ip_receiver_port=request.local_port,
            ip_receiver_account=request.mac,
            partitions_enabled=True # Assume true or handle dynamically if needed
        )
        
        if not success:
            raise HTTPException(status_code=503, detail=f"Failed to arm locally: {message}")

        new_status = "armed_away" if request.mode == ArmMode.AWAY else "armed_stay"
        
        return AlarmOperationResponse(
            success=True,
            device_id=device_id,
            partition_id=request.partition_id,
            new_status=new_status,
            message=f"Local arm command sent ({request.mode.value})"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error arming locally: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/disarm", response_model=AlarmOperationResponse)
async def disarm_local_partition(request: LocalDisarmRequest):
    """
    Disarm a partition directly using local IP Receiver protocol.
    Bypasses Intelbras Cloud API completely.
    """
    try:
        logger.info(f"Disarming locally MAC: {request.mac} at {request.local_ip}:{request.local_port} partition_index={request.partition_id}")

        device_id = 0
        mac_to_use = request.mac or ""
        success, message = await isecnet_client.disarm(
            device_id=device_id,
            mac=mac_to_use,
            password=request.password,
            partition_index=request.partition_id,
            use_ip_receiver=True,
            ip_receiver_addr=request.local_ip,
            ip_receiver_port=request.local_port,
            ip_receiver_account=request.mac,
            partitions_enabled=True
        )

        if not success:
            raise HTTPException(status_code=503, detail=f"Failed to disarm locally: {message}")

        return AlarmOperationResponse(
            success=True,
            device_id=device_id,
            partition_id=request.partition_id,
            new_status="disarmed",
            message="Local disarm command sent"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error disarming locally: {e}")
        raise HTTPException(status_code=500, detail=str(e))

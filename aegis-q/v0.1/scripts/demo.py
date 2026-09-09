from aegis_q.core import SensorFrame, RobotState, evaluate_security_state
from aegis_q.pqc_identity import DeviceIdentityEnvelope
from aegis_q.nvidia_adapter import NvidiaRuntimeDescriptor, build_runtime_plan

frames = [
    SensorFrame("u1-glasses","vision",1000,True,True,.94),
    SensorFrame("u1-watch","imu",1001,True,True,.91),
]
robot = RobotState("u1-robot","abc123","abc123",0.2,0.21)
state = evaluate_security_state(frames, robot)
identity = DeviceIdentityEnvelope("user","u1-watch","wearable","f"*64,"nonce-1234")
runtime = build_runtime_plan(NvidiaRuntimeDescriptor(runtime_digest_verified=False))

print({
    "security_state": state,
    "device_commitment": identity.sha3_commitment(),
    "nvidia_runtime": runtime,
})

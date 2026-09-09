from dataclasses import replace
from pathlib import Path
import json
import subprocess
import pytest
from aegis_q.core import SensorFrame, RobotState, evaluate_security_state
from aegis_q.pqc_identity import DeviceIdentityEnvelope, verify_reference_envelope

FRAME = SensorFrame('watch', 'imu', 1, True, True, .9)

@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), True, '0.1'])
def test_nonfinite_robot_and_sensor_telemetry(value):
    for field in ['commanded_speed_mps', 'observed_speed_mps']:
        robot = replace(RobotState('r', 'x', 'x', 0., 0.), **{field: value})
        assert evaluate_security_state([FRAME], robot).label == 'ROBOT_ANOMALY'
    assert evaluate_security_state([replace(FRAME, confidence=value)]).label == 'SPOOFED_SENSOR'
    assert evaluate_security_state([replace(FRAME, features=(value,))]).label == 'SPOOFED_SENSOR'

@pytest.mark.parametrize('kem,sig', [('ML-KEM-arbitrary','ML-DSA-65'), ('ML-KEM-768','ML-DSA-arbitrary'), ('ML-KEM-512','ML-DSA-65'), (None,None)])
def test_exact_pq_algorithm_allowlist(kem, sig):
    assert not verify_reference_envelope(DeviceIdentityEnvelope('u','d','watch','a'*64,'nonce-1234',kem,sig))

@pytest.mark.parametrize('motion,expected', [('0','NORMAL'), ('0.3','NORMAL'), ('0.300001','REVIEW'), ('0.5','REVIEW'), ('0.500001','ROBOT_ANOMALY'), ('NaN','ROBOT_ANOMALY'), ('Infinity','ROBOT_ANOMALY'), ('','ROBOT_ANOMALY')])
def test_browser_python_parity(motion, expected):
    html = (Path(__file__).parents[1] / 'index.html').read_text()
    script = html.split('<script>')[1].split('</script>')[0]
    program = 'const values={prov:{value:"good"},integrity:{value:"good"},firmware:{value:"good"},motion:{value:' + json.dumps(motion) + '},result:{innerHTML:""}};\nconst document={getElementById:(id)=>values[id]};\n' + script + '\nevaluateState(); console.log(values.result.innerHTML);'
    result = subprocess.run(['node','-e',program], capture_output=True, text=True, check=True)
    assert '>'+expected+'<' in result.stdout
    robot = RobotState('r', 'x', 'x', 0, float(motion) if motion else float('nan'))
    assert evaluate_security_state([FRAME], robot).label == expected

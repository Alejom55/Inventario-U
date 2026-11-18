from security.run_e1 import summarize


def test_missing_detection_and_containment_are_censored_not_zero():
    result=summarize([{'status':200}]*10,[{'status':201}]*10,None,None,30)
    assert result['mttd_seconds'] is None and result['mttd_censored']
    assert result['mttc_seconds'] is None and result['mttc_censored']
    assert result['objective']['passed'] is False
    assert result['detection_coverage_percent']==0 and result['adverse_acceptance_percent']==100


def test_detection_and_false_positives_have_distinct_denominators():
    result=summarize([{'status':200}]*9+[{'status':403}],[{'status':403}]*10,8,0.1,30)
    assert result['objective']['passed'] and result['containment_guardrail_passed']
    assert result['false_positive_percent']==10
    assert result['techniques_emulated']==result['techniques_detected']==1
    assert result['adverse_acceptance_percent']==0


def test_one_rejection_does_not_prove_sustained_containment():
    result=summarize([{'status':200}]*10,[{'status':403},{'status':201}],8,.1,30)
    assert result['mttc_seconds'] is None and result['mttc_censored']
    assert not result['containment_guardrail_passed']

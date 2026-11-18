import pytest
from datetime import datetime,timedelta,timezone

from deploy.aws.launch import validate_plan,validate_free_account,window_deadline


def test_aws_cost_reserve_requires_verified_price_and_revision():
    assert validate_plan(0.0208,'a'*40)<0.4
    for price,revision in [(0,'a'*40),(0.1,'a'*40),(0.0208,'main')]:
        with pytest.raises(ValueError):validate_plan(price,revision)


def test_aws_free_account_is_required_even_when_paid_accounts_have_credits():
    account={'accountPlanType':'FREE','accountPlanStatus':'ACTIVE',
        'accountPlanRemainingCredits':{'amount':100,'unit':'USD'},
        'accountPlanExpirationDate':datetime.now(timezone.utc)+timedelta(days=30)}
    assert validate_free_account(account)['maximum_out_of_pocket_usd']==0
    for changes in ({'accountPlanType':'PAID'},{'accountPlanStatus':'EXPIRED'},
                    {'accountPlanRemainingCredits':{'amount':0,'unit':'USD'}},
                    {'accountPlanExpirationDate':datetime.now(timezone.utc)+timedelta(hours=1)}):
        with pytest.raises(ValueError):validate_free_account({**account,**changes})


def test_explicit_demo_window_keeps_one_dollar_reserve_and_exact_deadline():
    now=datetime(2026,11,18,3,0,tzinfo=timezone.utc)
    assert window_deadline('2026-11-18T23:00:00Z',now)==now+timedelta(hours=20)
    assert validate_plan(.0208,'a'*40,20)<.8
    with pytest.raises(ValueError):validate_plan(.04,'a'*40,20)
    for value in ('2026-11-18T02:00:00Z','2026-11-18T23:00:00','2026-11-20T23:00:00Z'):
        with pytest.raises(ValueError):window_deadline(value,now)


def test_resource_target_requires_public_aws_origin_and_cannot_mix_clouds(monkeypatch):
    from chaos_lab.resource import target
    monkeypatch.setenv('CHAOS_ROUND','R1')
    monkeypatch.delenv('RESOURCE_RENDER_URL',raising=False)
    monkeypatch.setenv('RESOURCE_AWS_URL','https://8.8.8.8.sslip.io')
    assert target()==('R1','https://8.8.8.8.sslip.io')
    monkeypatch.setenv('RESOURCE_AWS_URL','https://127.0.0.1.sslip.io')
    with pytest.raises(ValueError):target()
    monkeypatch.setenv('RESOURCE_AWS_URL','https://8.8.8.8.sslip.io')
    monkeypatch.setenv('RESOURCE_RENDER_URL','https://test.onrender.com')
    with pytest.raises(ValueError):target()

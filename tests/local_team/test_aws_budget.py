import pytest

from deploy.aws.launch import validate_plan


def test_aws_cost_reserve_requires_verified_price_and_revision():
    assert validate_plan(0.0208,'a'*40)<0.4
    for price,revision in [(0,'a'*40),(0.1,'a'*40),(0.0208,'main')]:
        with pytest.raises(ValueError):validate_plan(price,revision)

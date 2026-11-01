import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_production_settings_require_explicit_secure_configuration():
    config=Settings(_env_file=None,secret_key='r'*48,app_environment='production',cors_origins='https://pocketwise.example',auto_migrate=False)
    assert config.app_environment=='production' and not config.auto_migrate
    for values in (
        {'secret_key':'short'},
        {'cors_origins':'*'},
        {'auto_migrate':True},
        {'cors_origins':'http://pocketwise.example'},
    ):
        params={'secret_key':'r'*48,'app_environment':'production','cors_origins':'https://pocketwise.example','auto_migrate':False,**values}
        with pytest.raises(ValidationError):
            Settings(_env_file=None,**params)

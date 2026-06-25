from ninja import ModelSchema
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

from .models import OIDCConfiguration, SiteMembership, StudyMembership, User, UserProfile


class UserProfileOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = UserProfile
        fields = ["id", "notifications_enabled"]


class UserProfileIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = UserProfile
        fields = ["notifications_enabled"]


class UserOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
    profile: UserProfileOut | None = None

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "is_active", "is_staff"]


class UserIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_active"]


class SiteMembershipOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = SiteMembership
        fields = ["id", "role"]


class SiteMembershipIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = SiteMembership
        fields = ["role"]


class StudyMembershipOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = StudyMembership
        fields = ["id", "role"]


class StudyMembershipIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = StudyMembership
        fields = ["role"]


class OIDCConfigurationOut(ModelSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)

    class Meta:
        model = OIDCConfiguration
        fields = ["id", "provider_name", "client_id", "discovery_url", "is_active"]


class OIDCConfigurationIn(ModelSchema):
    model_config = ConfigDict(extra="forbid")

    class Meta:
        model = OIDCConfiguration
        fields = ["provider_name", "client_id", "discovery_url", "is_active"]

"""TODO: Add a proper docstring here.

This is a placeholder docstring for this charm library. Docstrings are
presented on Charmhub and updated whenever you push a new version of the
library.

Complete documentation about creating and documenting libraries can be found
in the SDK docs at https://juju.is/docs/sdk/libraries.

See `charmcraft publish-lib` and `charmcraft fetch-lib` for details of how to
share and consume charm libraries. They serve to enhance collaboration
between charmers. Use a charmer's libraries for classes that handle
integration with their charm.

Bear in mind that new revisions of the different major API versions (v0, v1,
v2 etc) are maintained independently.  You can continue to update v0 and v1
after you have pushed v3.

Markdown is supported, following the CommonMark specification.
"""

import enum
import logging
import pickle
import typing

import charms.data_platform_libs.v1.data_interfaces as data_interfaces
import ops
import pydantic
import typing_extensions

# The unique Charmhub library identifier, never change it
LIBID = "7aafd08833414f9bb1fdef80f64d2755"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1


logger = logging.getLogger(__name__)

GIT_INTEGRATOR_ENDPOINT = "git"


class AuthenticationMethodEnum(str, enum.Enum):
    """Enum to encapsulate the possible Git authentication method options."""

    CREDENTIALS = "credentials"
    SSH = "ssh"


PersonalAccessTokenStr = typing.Annotated[
    data_interfaces.OptionalSecretStr, pydantic.Field(default=None), "personal-access-token"
]

SSHPrivateKeyStr = typing.Annotated[
    data_interfaces.OptionalSecretStr,
    pydantic.Field(default=None),
    "ssh-private-key",
]


class GitProviderModel(data_interfaces.BaseCommonModel):
    """Provider side of the git relation interface."""

    repository_url: str = pydantic.Field()
    path: str | None = pydantic.Field(default=None)
    tracking_ref: str | None = pydantic.Field(default=None)

    authentication_method: AuthenticationMethodEnum

    username: str | None = pydantic.Field(default=None)
    personal_access_token: PersonalAccessTokenStr = pydantic.Field(default=None)
    secret_personal_access_token: data_interfaces.SecretString = pydantic.Field(default=None)

    ssh_private_key: SSHPrivateKeyStr = pydantic.Field(default=None)
    secret_ssh_private_key: data_interfaces.SecretString = pydantic.Field(default=None)
    ssh_strict_host_key_checking: bool | None = pydantic.Field(default=None)

    # hack to enable databag diff computation with data_interfaces v1 charm lib
    request_id: str = pydantic.Field(default="fixed_request_id", exclude=True)


TGitProviderModel = typing.TypeVar("TGitProviderModel", bound=GitProviderModel)


class GitConnectionInformationUpdatedEvent(ops.EventBase, typing.Generic[TGitProviderModel]):
    """Git connection information updated event."""

    def __init__(
        self,
        handle: ops.Handle,
        relation: ops.Relation,
        app: ops.Application | None,
        unit: ops.Unit | None,
        content: TGitProviderModel,
    ):
        super().__init__(handle)
        self.relation = relation
        self.app = app
        self.unit = unit
        self.content = content

    def snapshot(self) -> dict[str, typing.Any]:
        """Save event information."""
        snapshot = {
            "relation_name": self.relation.name,
            "relation_id": self.relation.id,
        }

        if self.app:
            snapshot["app_name"] = self.app.name
        if self.unit:
            snapshot["unit_name"] = self.unit.name

        # Easier to pickle than disect content marshalling. The snapshot dictionary
        # is pickled by ops anyhow.
        snapshot["content"] = pickle.dumps(self.content)

        return snapshot

    def restore(self, snapshot: dict[str, typing.Any]):
        """Restore event information."""
        relation = self.framework.model.get_relation(
            snapshot["relation_name"], snapshot["relation_id"]
        )
        if not relation:
            raise ValueError("Missing relation")

        self.relation = relation

        app_name = snapshot.get("app_name")
        self.app = self.framework.model.get_app(app_name) if app_name else None

        unit_name = snapshot.get("unit_name")
        self.unit = self.framework.model.get_unit(unit_name) if unit_name else None

        self.content = pickle.loads(snapshot["content"])


class GitProvidesEvents(ops.CharmEvents, typing.Generic[TGitProviderModel]):
    """Events that Git provider can emit."""

    git_connection_information_updated = ops.EventSource(GitConnectionInformationUpdatedEvent)


class GitRequirerEventHandler(data_interfaces.EventHandlers, typing.Generic[TGitProviderModel]):
    """Event Handler for Git requirer."""

    on = GitProvidesEvents[TGitProviderModel]()

    def __init__(
        self,
        charm: ops.CharmBase,
        relation_name: str,
        request_model: type[TGitProviderModel],
        unique_key: str = "",
    ):
        """Builds an Git requirer event handler."""
        super().__init__(charm, relation_name, unique_key)
        self.charm = charm
        self.component = self.charm.app
        self.request_model = request_model
        self.interface = data_interfaces.OpsRelationRepositoryInterface(
            charm.model, relation_name, request_model
        )

        self.relation = self.charm.model.get_relation(relation_name)
        self.repository = (
            data_interfaces.OpsRelationRepository(
                self.model, self.relation, component=self.relation.app
            )
            if self.relation
            else None
        )

    def _dispatch_events(
        self,
        event: ops.RelationEvent,
        _diff: data_interfaces.Diff,
        content: GitProviderModel,
    ):
        if any(
            key in _diff.added or key in _diff.changed
            for key in [
                "repository-url",
                "path",
                "tracking-ref",
                "authentication-method",
                "username",
                "personal_access_token",
                "ssh-private-key",
                "ssh-strict-host-key-checking",
            ]
        ):
            getattr(self.on, "git_connection_information_updated").emit(
                event.relation, app=event.app, unit=event.unit, content=content
            )

    @typing_extensions.override
    def _handle_event(
        self,
        event: ops.RelationChangedEvent,
        repository: data_interfaces.AbstractRepository,
        content: GitProviderModel,
    ):
        _diff = self.compute_diff(event.relation, content, repository)

        self._dispatch_events(event, _diff, content)

    @typing_extensions.override
    def _on_secret_changed_event(self, event: ops.SecretChangedEvent) -> None:
        if not event.secret.label:
            return

        relation = self._relation_from_secret_label(event.secret.label)
        short_uuid = self._short_uuid_from_secret_label(event.secret.label)

        if not short_uuid:
            return

        if not relation:
            logging.warning(
                f"Received secret {event.secret.label} but couldn't parse, seems irrelevant"
            )
            return

        if relation.name != self.relation_name:
            logging.warning("Secret changed on wrong relation")
            return

        try:
            event.secret.get_info()
            logging.warning("Secret changed event ignored for Secret Owner")
            return
        except ops.SecretNotFoundError:
            pass

        remote_unit = self.get_remote_unit(relation)

        try:
            content = self.interface.build_model(
                self.relation.id, GitProviderModel, component=self.relation.app
            )
        except pydantic.ValidationError as e:
            logger.warning(f"Invalid relation contents from the git integrator charm: {e}")
            return

        getattr(self.on, "git_connection_information_updated").emit(
            relation,
            app=relation.app,
            unit=remote_unit,
            content=content,
        )

    @typing_extensions.override
    def _on_relation_changed_event(self, event: ops.RelationChangedEvent) -> None:
        if not self.charm.unit.is_leader():
            return

        repository = data_interfaces.OpsRelationRepository(
            self.model, event.relation, component=event.relation.app
        )

        try:
            content = self.interface.build_model(
                self.relation.id, GitProviderModel, component=self.relation.app
            )
        except pydantic.ValidationError as e:
            logger.warning(f"Invalid relation contents from the git integrator charm: {e}")
            return

        self._handle_event(event, repository, content)

    @property
    def provider_content(self) -> dict[str, str]:
        """Data from the related git integrator charm."""
        if not self.relation:
            return {}

        try:
            model = self.interface.build_model(
                self.relation.id, GitProviderModel, component=self.relation.app
            )
            content = model.model_dump(
                exclude={"secret_personal_access_token", "secret_ssh_private_key"}
            )

            return {key: value for key, value in content.items() if value is not None}
        except pydantic.ValidationError:
            return {}


class GitProviderEventHandler(data_interfaces.EventHandlers, typing.Generic[TGitProviderModel]):
    """Event Handler for Git provider."""

    def __init__(
        self,
        charm: ops.CharmBase,
        relation_name: str,
        unique_key: str = "",
    ):
        """Builds an Git provider event handler."""
        super().__init__(charm, relation_name, unique_key)
        self.component = self.charm.app

        self.interface = data_interfaces.OpsRelationRepositoryInterface(
            charm.model, relation_name, TGitProviderModel
        )

    @typing_extensions.override
    def _on_relation_changed_event(self, event: ops.RelationChangedEvent) -> None:
        pass

    def update_git_connection_info(
        self,
        connection_info: dict[str, str],
    ):
        """Update data to send to related charms."""
        if not self.interface.relations:
            return

        if not connection_info:
            return

        if not self.charm.unit.is_leader():
            return

        filtered_connection_info = {
            key: value for key, value in connection_info.items() if not key.startswith("secret")
        }

        for relation in self.interface.relations:
            model = None

            if self.interface.repository(relation.id, self.charm.app).get_data():
                try:
                    model = self.interface.build_model(
                        relation.id, GitProviderModel, component=self.charm.app
                    ).model_copy(update=filtered_connection_info)

                    if (
                        connection_info.get("authentication_method")
                        == AuthenticationMethodEnum.CREDENTIALS
                    ):
                        model.ssh_private_key = "None"
                        model.ssh_strict_host_key_checking = None
                    elif (
                        connection_info.get("authentication_method")
                        == AuthenticationMethodEnum.SSH
                    ):
                        model.username = None
                        model.personal_access_token = "None"

                except pydantic.ValidationError:
                    pass

            if not model:
                model = GitProviderModel(**filtered_connection_info)

            self.interface.write_model(relation.id, model)


class GitRequires(ops.Object):
    """A requirer handler encapsulating the git relation."""

    def __init__(
        self,
        charm: ops.CharmBase,
        relation_name: str,
        callback: typing.Callable,
    ):
        super().__init__(charm, relation_name)

        self._requirer_handler = GitRequirerEventHandler(charm, relation_name, GitProviderModel)
        self._provider_content = self._requirer_handler.provider_content

        for event in [
            self._requirer_handler.on.git_connection_information_updated,
            charm.on[relation_name].relation_broken,
        ]:
            self.framework.observe(event, callback)

    def get_git_connection_information(self) -> dict[str, str]:
        """The git connection information from the relation."""
        if not self._provider_content:
            return {}

        git_connection_information = {
            "repository_url": self.repository_url,
            "authentication_method": self.authentication_method,
        }

        if self.path:
            git_connection_information["path"] = self.path

        if self.tracking_ref:
            git_connection_information["tracking_ref"] = self.tracking_ref

        if self.authentication_method == AuthenticationMethodEnum.CREDENTIALS:
            git_connection_information["credentials"] = self.credentials

        if self.authentication_method == AuthenticationMethodEnum.SSH:
            git_connection_information["ssh"] = {
                "private_key": self.ssh_private_key,
                "strict_host_key_checking": self.strict_host_key_checking,
            }

        # Ensure non-nullness of expected git connection info
        if any(
            value is None if not isinstance(value, dict) else None in value.values()
            for value in git_connection_information.values()
            if not isinstance(value, dict)
        ):
            return {}

        return git_connection_information

    @property
    def repository_url(self) -> typing.Optional[str]:
        """The git repository url."""
        return self._provider_content.get("repository-url")

    @property
    def path(self) -> typing.Optional[str]:
        """The path within the git repository."""
        return self._provider_content.get("path")

    @property
    def tracking_ref(self) -> typing.Optional[str]:
        """The git repository tracking ref."""
        return self._provider_content.get("tracking-ref")

    @property
    def authentication_method(self) -> typing.Optional[str]:
        """The git repository authentication method."""
        return self._provider_content.get("authentication-method")

    @property
    def credentials(self) -> dict[str, str]:
        """The git repository credentials."""
        if self.authentication_method != AuthenticationMethodEnum.CREDENTIALS:
            return {}

        return {
            "username": self._provider_content.get("username"),
            "personal_access_token": self._provider_content.get("personal-access-token"),
        }

    @property
    def ssh_private_key(self) -> typing.Optional[str]:
        """The git repository authentication SSH private key."""
        return self._provider_content.get("ssh-private-key")

    @property
    def strict_host_key_checking(self) -> typing.Optional[bool]:
        """Strict host key checking indicator for the git repository."""
        ssh_strict_host_key_checking = self._provider_content.get("ssh-strict-host-key-checking")
        if ssh_strict_host_key_checking is None:
            return None

        return ssh_strict_host_key_checking == "true"


class GitProvides(ops.Object):
    """A provider handler encapsulating the git relation."""

    def __init__(
        self,
        charm: ops.CharmBase,
        relation_name: str,
        callback: typing.Callable,
    ):
        super().__init__(charm, relation_name)

        self.framework.observe(charm.on[relation_name].relation_broken, callback)

        if not charm.model.relations.get(relation_name):
            self._provider_handler = None
            return

        self._provider_handler = GitProviderEventHandler(charm, relation_name)

    def update_git_connection_info(self, connection_info: dict[str, str]):
        """Update git connection info appropriately in all relations."""
        if not self._provider_handler:
            return

        self._provider_handler.update_git_connection_info(connection_info)

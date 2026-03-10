"""Library to manage the relation provided by the Git Integrator charm.

This library contains the Requires and Provides classes for handling the relation
between provider of the git relation interface (Git Integrator) and also the requirers.
Both the Requires and Provides classes supports multiple relations over the git
interfaces (the Git Integrator charm can share data with multiple downstream requirer
apps, and similarly, a requirer app can receive data from multiple upstream Git
Integrator charms.)

### Requirer Charm

The following presents an example usage of the GitIntegratorRequires class:

```python
import charms.git_integrator.v0.git as git


class CharmThatNeedsGit(ops.CharmBase):
    def __init__(self, *args) -> None:
        super().__init__(*args)

        self.git_requirer = git.GitRequires(
            self,
            "git", # relation endpoint
            callback=self.reconcile,
        )

        self.framework.observer(
            self.git_requirer.on.git_connection_information_update,
            self.print_git_connection_information,
        )

    def reconcile(self, event) -> None:
        # Reconciler method for this charm

        self.git_requirer.get_git_connection_information() # dict with git connection details

        # git connection details of a specific relation
        git_relations = self.model.relations["git"]
        for relation in git_relations:
            self.git_requirer.get_git_connection_information_for_relation(relation.id)


    def print_git_connection_information(self) -> None:
        # Print the git connection information
        print(f"New git connection info: {self.git_requirer.get_connection_information()}")


### Provider Charm

The following presents an example usage of the GitProvides class:

```python
import charms.git_integrator.v0.git as git


class GitIntegrator(ops.CharmBase):
    def __init__(self, *args) -> None:
        super().__init__(*args)

        self.git_provider = git.GitProvides(
            self,
            "git", # relation endpoint
            self.reconcile,
        )

    def reconcile(self, event) -> None:
        # Reconciler method for this charm

        self.git_provider.update_git_connection_information({
            "repository_url": "https://github.com/my/repo",
            "path": "custom/sub/directory",
        })
```
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


class AuthenticationMethodEnum(enum.StrEnum):
    """Enum to encapsulate the possible Git authentication method options."""

    CREDENTIALS = "credentials"
    SSH = "ssh"


PersonalAccessTokenStr = typing.Annotated[
    data_interfaces.OptionalSecretStr,
    pydantic.Field(default=None, exclude=True),
    "personal-access-token",
]

SSHPrivateKeyStr = typing.Annotated[
    data_interfaces.OptionalSecretStr,
    pydantic.Field(default=None, exclude=True),
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
                "personal-access-token",
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
                relation.id, GitProviderModel, component=relation.app
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
                event.relation.id, GitProviderModel, component=event.relation.app
            )
        except pydantic.ValidationError as e:
            logger.warning(f"Invalid relation contents from the git integrator charm: {e}")
            return

        self._handle_event(event, repository, content)

    @property
    def provider_content(self) -> dict[int, GitProviderModel]:
        """Data from the related git integrator charms."""
        try:
            return {
                relation.id: self.interface.build_model(
                    relation.id, GitProviderModel, component=relation.app
                )
                for relation in self.charm.model.relations[self.relation_name]
            }
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
        callback: typing.Optional[typing.Callable] = None,
    ):
        super().__init__(charm, relation_name)

        self._requirer_handler = GitRequirerEventHandler(charm, relation_name, GitProviderModel)
        self._provider_content = self._requirer_handler.provider_content
        self._relations = charm.model.relations[relation_name]

        if callback:
            for event in [
                self._requirer_handler.on.git_connection_information_updated,
                charm.on[relation_name].relation_broken,
            ]:
                self.framework.observe(event, callback)

    @property
    def on(self) -> GitProvidesEvents[TGitProviderModel]:
        """ops.CharmEvents containing custom events for this relation."""
        return self._requirer_handler.on

    @property
    def relations(self) -> list[ops.Relation]:
        """Relations for the git interface."""
        return list(self._relations)

    def get_git_connection_information_for_relation(self, relation_id: int) -> dict:
        """The git connection information for a relation."""
        content = self._provider_content.get(relation_id)
        if not content:
            return {}

        git_connection_information = {
            "repository_url": content.repository_url,
            "authentication_method": content.authentication_method.value,
        }

        if content.path:
            git_connection_information["path"] = content.path

        if content.tracking_ref:
            git_connection_information["tracking_ref"] = content.tracking_ref

        if content.authentication_method == AuthenticationMethodEnum.CREDENTIALS:
            git_connection_information["credentials"] = {
                "username": content.username,
                "personal_access_token": content.personal_access_token,
            }

        if content.authentication_method == AuthenticationMethodEnum.SSH:
            git_connection_information["ssh"] = {
                "private_key": content.ssh_private_key,
                "strict_host_key_checking": content.ssh_strict_host_key_checking,
            }

        return dict(sorted(git_connection_information.items(), key=lambda item: item[0]))

    def get_git_connection_information(self) -> dict[int, dict]:
        """Git connection information for all relations."""
        return {
            relation_id: self.get_git_connection_information_for_relation(relation_id)
            for relation_id in self._provider_content
        }


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

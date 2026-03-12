# Contributing

To make contributions to this charm, you'll need a working
[development setup](https://documentation.ubuntu.com/juju/3.6/howto/manage-your-deployment/#set-up-your-deployment-local-testing-and-development).


## Testing

This project uses `just` for managing development routines. There are some targets
that can be used for linting and formatting code when you're preparing
contributions to the charm:

```shell
just format       # update your code according to linting rules
just lint         # code style
just unit         # unit tests
```

## Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack
```

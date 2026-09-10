# Before publishing or releasing

The repository includes project files, not a guarantee that GitHub settings have
been enabled. On the actual repository:

- Enable private vulnerability reporting under Security. Add a private maintainer
  contact route for code-of-conduct reports; do not invent an email address.
- Enable secret scanning and push protection where available. Inspect the complete
  staged diff and Git history for credentials and personal content before pushing.
- Confirm the MIT license matches your intended release policy. The working tree
  contains the MIT license; keep all documentation consistent with that file.
- Enable Actions, require passing CI on pull requests, and configure branch protection.
- Replace any hosting-specific references if renaming or moving the repository.
  The documentation uses relative local links to stay portable across forks.
- Check the setup guide from a fresh checkout with no `.env`, `data/`, or legacy
  profile files. Only fictional data should appear in screenshots and fixtures.
- Build the container and test login, draft generation, decline, regeneration and
  approval on your own accounts. The offline suite does not establish API access.
- Review dependency updates and provider API changes. The current requirements use
  compatible version ranges rather than a fully reproducible dependency lock.
- Update CHANGELOG.md and create a release only after checking the supported path.

There is no usable Git repository metadata in the preparation workspace, so its
history could not be audited there. Existing `.env` and `data/` were kept local.
If publishing a Git history from another checkout, inspect that history too.

## Existing-installation migration

Run `python3 scripts/setup.py` before rebuilding this version. It copies legacy
root `profile.md` and `previous_post.md` into `data/` only when the destination does
not exist. It leaves existing `.env`, database, cache and personal files intact.
Compose now mounts `data/` for both services; personal profiles are not baked into
the image. Back up `data/` before upgrades.

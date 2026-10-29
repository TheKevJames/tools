#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "cryptography==50.0.2",
# ]
# ///
"""
Derive a reproducible Ed25519 OpenSSH key from a passphrase.

Setup (on a target machine):

    uv run cli.py >> ~/.ssh/authorized_keys

Emergency (on your local machine):

    uv run cli.py --private | ssh-add -

Needs approx ~1GiB of free RAM, based on the hardcoded constants below. Note
that those constants control the determinism -- you can tweak them if you'd
like, but make sure you keep a reference to the values you used to generate the
key in the first place!

    passphrase --Argon2id(1 GiB, t=8, p=1, salt=label)--> 32-byte seed
    seed --> Ed25519 keypair --> OpenSSH key format
"""

import argparse
import getpass
import sys
import unicodedata

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

# ---- Key-derivation parameters: do not change after you deploy a key ------
ARGON2_MEMORY_KIB = 2**20  # 1 GiB
ARGON2_ITERATIONS = 8
ARGON2_LANES = 1
DEFAULT_LABEL = 'emergency'
DOMAIN = b'deterministic-ssh/v1\0'  # domain separation for the salt
# ---------------------------------------------------------------------------


def derive_seed(
    passphrase: str,
    label: str,
    memory_kib: int = ARGON2_MEMORY_KIB,
    iterations: int = ARGON2_ITERATIONS,
) -> bytes:
    pw = unicodedata.normalize('NFKC', passphrase).encode('utf-8')
    return Argon2id(
        salt=DOMAIN + label.encode('utf-8'),
        length=32,
        iterations=iterations,
        lanes=ARGON2_LANES,
        memory_cost=memory_kib,
    ).derive(pw)


def public_line(key: Ed25519PrivateKey) -> str:
    """'ssh-ed25519 AAAA...'."""
    return (
        key.public_key()
        .public_bytes(
            serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
        )
        .decode()
    )


def private_openssh(key: Ed25519PrivateKey) -> str:
    # Note: the library picks a random check value, so this text differs
    # between runs even though it encodes the same key.
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    ).decode()


def main() -> None:
    summary = __doc__.split('\n\n', maxsplit=1)[0]
    ap = argparse.ArgumentParser(description=summary)
    ap.add_argument(
        '-l',
        '--label',
        default=DEFAULT_LABEL,
        help='salt/comment for the key (default: %(default)s)',
    )
    ap.add_argument(
        '-p', '--private', action='store_true', help='print private key'
    )
    ap.add_argument(
        '--force',
        action='store_true',
        help='allow printing the private key to a terminal',
    )
    args = ap.parse_args()

    if args.private and sys.stdout.isatty() and not args.force:
        sys.exit(
            'refusing to print a private key to a terminal; pipe it '
            '(e.g. "| ssh-add -") or use --force'
        )

    pw = getpass.getpass('passphrase: ')
    if getpass.getpass('passphrase (repeat): ') != pw:
        sys.exit('passphrases do not match')

    print(
        'deriving key (about 1 GiB of RAM, may take ~10 seconds)...',
        file=sys.stderr,
    )
    key = Ed25519PrivateKey.from_private_bytes(derive_seed(pw, args.label))

    if args.private:
        sys.stdout.write(private_openssh(key))
    else:
        print(f'{public_line(key)} {args.label}')


if __name__ == '__main__':
    sys.exit(main())

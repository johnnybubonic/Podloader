#!/usr/bin/env python3.6

# stdlib
import os
import re
# pypi
import gpg
import gpg.constants
import gpg.errors

# Re-sign all episode files that have an invalid signature.

# The GPG home
GNUPGHOME = '~/podcast/gpg'
# The key ID to use to sign/verify. Must exist in the local keyring, trusted, etc.
GPGKEY = '0x63D1CEA387C27A92E0D50AB8343C305F9109D4DC'
# The "parent" path that contains both audio files and detached sigs.
# It is assumed that the sigs for each episode file live in ../gpg/* (relative
# to the media file(s)).
# If you need to change this, check the signer class.
EPPATH = '~/podcast/releases'
FILEEXTS = ('mp3', 'ogg')

class signer(object):
    def __init__(self, key_id, gpg_home = '~/.gnupg',
                 sig_ext = '.asc', gpg_armor = True):
        os.environ['GNUPGHOME'] = os.path.abspath(os.path.expanduser(gpg_home))
        self.sig_ext = sig_ext
        self.gpg = gpg.Context()
        # has to be an iterable
        self.gpg.signers = []
        self.key = self.gpg.get_key(key_id, True)
        if self.key.can_sign:
            self.gpg.signers.append(self.key)
        self.gpg.armor = True

    def chkSigValid(self, fpath, sigpath_base):
        sigpath = '.'.join((sigpath_base, re.sub('^\.', '', self.sig_ext)))
        with open(sigpath, 'rb') as sig, open(fpath, 'rb') as f, \
                                         open(os.devnull, 'wb') as DEVNULL:
            try:
                self.gpg.verify(f, signature = sig, sink = DEVNULL,
                                verify = self.gpg.signers)
                return(True)
            except (gpg.errors.BadSignatures, gpg.errors.GPGMEError,
                    FileNotFoundError):
                print('BAD/MISSING SIGNATURE: {0}'.format(fpath))
                return(False)

    def signEpFile(self, fpath, sigpath_base):
        sigpath = '.'.join((sigpath_base, re.sub('^\.', '', self.sig_ext)))
        with open(sigpath, 'wb') as f, open(fpath, 'rb') as s:
            f.write(self.gpg.sign(s, mode = gpg.constants.SIG_MODE_DETACH)[0])
        print('Signed/re-signed {0}'.format(fpath))
        return()

def getEpFiles(path, exts):
    print('Building list of media files; please wait...')
    fpaths = []
    path = os.path.abspath(os.path.expanduser(path))
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.endswith(exts):
                fpaths.append(os.path.join(root, f))
    return(fpaths)

def main(GPGHOME = GNUPGHOME, KEYID = GPGKEY,
         EPSPATH = EPPATH, FILEEXT = FILEEXTS):
    fpaths = getEpFiles(EPSPATH, FILEEXT)
    sig = signer(KEYID, gpg_home = GPGHOME)
    print('Verifying files (and signing if necessary)...')
    for f in fpaths:
        sigfilebase = os.path.abspath(
                        os.path.join(
                            os.path.dirname(f),
                            os.path.join('..',
                                         'gpg',
                                         os.path.basename(f))))
        if not sig.chkSigValid(f, sigfilebase):
            sig.signEpFile(f, sigfilebase)

if __name__ == '__main__':
    main()

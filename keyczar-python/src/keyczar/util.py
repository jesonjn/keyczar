#!/usr/bin/python2.4
#
# Copyright 2008 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#      http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Utility functions for keyczar package.

@author: arkajit.dey@gmail.com (Arkajit Dey)
"""

import base64
import math
import sha

from Crypto.Util import randpool
from pyasn1.codec.der import decoder
from pyasn1.codec.der import encoder
from pyasn1.type import univ

import errors

HLEN = sha.digest_size  # length of the hash output

#RSAPrivateKey ::= SEQUENCE {
#  version Version,
#  modulus INTEGER, -- n
#  publicExponent INTEGER, -- e
#  privateExponent INTEGER, -- d
#  prime1 INTEGER, -- p
#  prime2 INTEGER, -- q
#  exponent1 INTEGER, -- d mod (p-1)
#  exponent2 INTEGER, -- d mod (q-1)
#  coefficient INTEGER -- (inverse of q) mod p }
#
#Version ::= INTEGER
RSA_OID = univ.ObjectIdentifier('1.2.840.113549.1.1.1')
RSA_PARAMS = ['n', 'e', 'd', 'p', 'q', 'dp', 'dq', 'invq']
DSA_OID = univ.ObjectIdentifier('1.2.840.10040.4.1')
DSA_PARAMS = ['p', 'q', 'g']  # only algorithm params, not public/private keys

#PrivateKeyInfo ::= SEQUENCE {
#  version Version,
#
#  privateKeyAlgorithm PrivateKeyAlgorithmIdentifier,
#  privateKey PrivateKey,
#  attributes [0] IMPLICIT Attributes OPTIONAL }
#
#Version ::= INTEGER
#
#PrivateKeyAlgorithmIdentifier ::= AlgorithmIdentifier
#
#PrivateKey ::= OCTET STRING
#
#Attributes ::= SET OF Attribute
def ParsePkcs8(pkcs8):
  seq = decoder.decode(Decode(pkcs8))[0]
  if len(seq) != 3:  # need three fields in PrivateKeyInfo
    raise errors.KeyczarError("Illegal PKCS8 String.")
  version = int(seq.getComponentByPosition(0))
  if version != 0:
      raise errors.KeyczarError("Unrecognized PKCS8 Version")
  oid = seq.getComponentByPosition(1).getComponentByPosition(0)
  alg_params = seq.getComponentByPosition(1).getComponentByPosition(1)
  key = decoder.decode(seq.getComponentByPosition(2))[0]
  # Component 2 is an OCTET STRING which is further decoded
  params = {}
  if oid == RSA_OID:
    version = int(key.getComponentByPosition(0))
    if version != 0:
      raise errors.KeyczarError("Unrecognized RSA Private Key Version")
    for i in range(len(RSA_PARAMS)):
      params[RSA_PARAMS[i]] = long(key.getComponentByPosition(i+1))
  elif oid == DSA_OID:
    for i in range(len(DSA_PARAMS)):
      params[DSA_PARAMS[i]] = long(alg_params.getComponentByPosition(i))
    params['x'] = long(key)
  else:
    raise errors.KeyczarError("Unrecognized AlgorithmIdentifier: not RSA/DSA")
  return params

def ExportRsaPkcs8(params):
  seq = univ.Sequence().setComponentByPosition(0, univ.Integer(0))  # version
  oid = univ.Sequence().setComponentByPosition(0, RSA_OID)
  oid.setComponentByPosition(1, univ.Null())
  key = univ.Sequence().setComponentByPosition(0, univ.Integer(0))  # version
  for i in range(len(RSA_PARAMS)):
    key.setComponentByPosition(i+1, univ.Integer(params[RSA_PARAMS[i]]))
  octkey = encoder.encode(key)
  seq.setComponentByPosition(1, oid)
  seq.setComponentByPosition(2, univ.OctetString(octkey))
  return Encode(encoder.encode(seq))

def ExportDsaPkcs8(params):
  seq = univ.Sequence().setComponentByPosition(0, univ.Integer(0))  # version
  alg_params = univ.Sequence()
  for i in range(len(DSA_PARAMS)):
    alg_params.setComponentByPosition(i, univ.Integer(params[DSA_PARAMS[i]]))
  oid = univ.Sequence().setComponentByPosition(0, DSA_OID)
  oid.setComponentByPosition(1, alg_params)
  octkey = encoder.encode(univ.Integer(params['x']))
  seq.setComponentByPosition(1, oid)
  seq.setComponentByPosition(2, univ.OctetString(octkey))
  return Encode(encoder.encode(seq))

#NOTE: not full X.509 certificate, just public key info
#SubjectPublicKeyInfo  ::=  SEQUENCE  {
#        algorithm            AlgorithmIdentifier,
#        subjectPublicKey     BIT STRING  }
def ParseX509(x509):
  seq = decoder.decode(Decode(x509))[0]
  if len(seq) != 2:  # need two fields in SubjectPublicKeyInfo
    raise errors.KeyczarError("Illegal X.509 String.")
  oid = seq.getComponentByPosition(0).getComponentByPosition(0)
  alg_params = seq.getComponentByPosition(0).getComponentByPosition(1)
  pubkey = decoder.decode(univ.OctetString(BinToBytes(seq.
                            getComponentByPosition(1).prettyPrint()[1:-2])))[0]
  # Component 1 should be a BIT STRING, get raw bits by discarding extra chars,
  # then convert to OCTET STRING which can be ASN.1 decoded
  params = {}
  if oid == RSA_OID:
    params['n'] = long(pubkey.getComponentByPosition(0))
    params['e'] = long(pubkey.getComponentByPosition(1))
  elif oid == DSA_OID:
    for i in range(len(DSA_PARAMS)):
      params[DSA_PARAMS[i]] = long(alg_params.getComponentByPosition(i))
    params['y'] = long(pubkey)
  else:
    raise errors.KeyczarError("Unrecognized AlgorithmIdentifier: not RSA/DSA")
  return params

def ExportRsaX509(params):
  seq = univ.Sequence()
  oid = univ.Sequence().setComponentByPosition(0, RSA_OID)
  oid.setComponentByPosition(1, univ.Null())
  key = univ.Sequence()
  key.setComponentByPosition(0, univ.Integer(params['n']))
  key.setComponentByPosition(1, univ.Integer(params['e']))
  binkey = BytesToBin(encoder.encode(key))
  pubkey = univ.BitString("'%s'B" % binkey)  # needs to be a BIT STRING
  seq.setComponentByPosition(0, oid)
  seq.setComponentByPosition(1, pubkey)
  return Encode(encoder.encode(seq))

def ExportDsaX509(params):
  seq = univ.Sequence()
  alg_params = univ.Sequence()
  for i in range(len(DSA_PARAMS)):
    alg_params.setComponentByPosition(i, univ.Integer(params[DSA_PARAMS[i]]))
  oid = univ.Sequence().setComponentByPosition(0, DSA_OID)
  oid.setComponentByPosition(1, alg_params)
  binkey = BytesToBin(encoder.encode(univ.Integer(params['y'])))
  pubkey = univ.BitString("'%s'B" % binkey)  # needs to be a BIT STRING
  seq.setComponentByPosition(0, oid)
  seq.setComponentByPosition(1, pubkey)
  return Encode(encoder.encode(seq))

def MakeDsaSig(r, s):
  """
  Given the raw parameters of a DSA signature, return a Base64 signature.
  
  @param r: parameter r of DSA signature
  @type r: long int
  
  @param s: parameter s of DSA signature
  @type s: long int
  
  @return: raw byte string formatted as an ASN.1 sequence of r and s
  @rtype: string   
  """
  seq = univ.Sequence()
  seq.setComponentByPosition(0, univ.Integer(r))
  seq.setComponentByPosition(1, univ.Integer(s))
  return encoder.encode(seq)

def ParseDsaSig(sig):
  """
  Given a raw byte string, return tuple of DSA signature parameters.
  
  @param sig: byte string of ASN.1 representation
  @type sig: string
  
  @return: parameters r, s as a tuple
  @rtype: tuple
  
  @raise KeyczarErrror: if the DSA signature format is invalid 
  """
  seq = decoder.decode(sig)[0]
  if len(seq) != 2:
    raise errors.KeyczarError("Illegal DSA signature.")
  r = long(seq.getComponentByPosition(0))
  s = long(seq.getComponentByPosition(1))
  return (r, s)

def BinToBytes(bits):
  """Convert bit string to byte string."""
  bits = _PadByte(bits)
  octets = [bits[8*i:8*(i+1)] for i in range(len(bits)/8)]
  bytes = [chr(int(x, 2)) for x in octets]
  return "".join(bytes)

def BytesToBin(bytes):
  """Convert byte string to bit string."""
  return "".join([_PadByte(IntToBin(ord(byte))) for byte in bytes])

def _PadByte(bits):
  """Pad a string of bits with zeros to make its length a multiple of 8."""
  r = len(bits) % 8
  return ((8-r) % 8)*'0' + bits

def IntToBin(n):
  if n == 0 or n == 1:
    return str(n)
  elif n % 2 == 0:
    return IntToBin(n/2) + "0"
  else:
    return IntToBin(n/2) + "1"

def IntToBytes(n):
  """Return byte string of 4 big-endian ordered bytes representing n."""
  bytes = [m % 256 for m in [n >> 24, n >> 16, n >> 8, n]]
  return "".join([chr(b) for b in bytes])  # byte array to byte string

def BytesToInt(bytes):
  l = len(bytes)
  return sum([ord(bytes[i]) * 256**(l - 1 - i) for i in range(l)])

def Xor(a, b):
  """Return a ^ b as a byte string where a and b are byte strings."""
  # pad shorter byte string with zeros to make length equal
  m = max(len(a), len(b))
  a = _PadBytes(a, m - len(a))
  b = _PadBytes(b, m - len(b))
  x = [ord(c) for c in a]
  y = [ord(c) for c in b]
  z = [chr(x[i] ^ y[i]) for i in range(m)]
  return _TrimBytes("".join(z))
  
def _PadBytes(bytes, n):
  """Prepend a byte string with n zero bytes."""
  return n * chr(0) + bytes

def _TrimBytes(bytes):
  """Trim leading zero bytes."""
  trimmed = bytes.lstrip(chr(0))
  if trimmed == "":  # was a string of all zero bytes
    return chr(0)
  else:
    return trimmed

def RandBytes(n):
  """Return n random bytes."""
  return randpool.RandomPool(512).get_bytes(n)

def Hash(*inputs):
  """Return a SHA-1 hash over a variable number of inputs."""
  md = sha.new()
  for i in inputs:
    md.update(i)
  return md.digest()

def Encode(s):
  """
  Return Base64 encoding of s. Suppress padding characters (=).
  
  Uses URL-safe alphabet: - replaces +, _ replaces /. Will convert s of type
  unicode to string type first.
  
  @param s: string to encode as Base64
  @type s: string
  
  @return: Base64 representation of s.
  @rtype: string
  """
  return base64.urlsafe_b64encode(str(s)).replace("=", "")
  

def Decode(s):
  """
  Return decoded version of given Base64 string. Ignore whitespace.
  
  Uses URL-safe alphabet: - replaces +, _ replaces /. Will convert s of type
  unicode to string type first.
  
  @param s: Base64 string to decode
  @type s: string
  
  @return: original string that was encoded as Base64
  @rtype: string
  
  @raise Base64DecodingError: If length of string (ignoring whitespace) is one 
    more than a multiple of four.
  """
  s = str(s.replace(" ", ""))  # kill whitespace, make string (not unicode)
  d = len(s) % 4
  if d == 1:
    raise errors.Base64DecodingError()
  elif d == 2:
    s += "=="
  elif d == 3:
    s += "="
  return base64.urlsafe_b64decode(s)

def WriteFile(data, loc):
  try:
    f = open(loc, "w")
    f.write(data)
    f.close()
  except IOError:
    raise errors.KeyczarError("Bad file name")

def MGF(seed, mlen):
  """
  Mask Generation Function (MGF1) with SHA-1 as hash.
  
  @param seed: used to generate mask, a byte string
  @type seed: string
  
  @param mlen: desired length of mask
  @type mlen: integer
  
  @return: mask, byte string of length mlen
  @rtype: string
  
  @raise KeyczarError: if mask length too long, > 2^32 * hash_length  
  """
  if mlen > 2**32 * HLEN:
    raise errors.KeyczarError("MGF1 mask length too long.")
  return ("".join([Hash(seed, IntToBytes(i))
                   for i in range(int(math.ceil(mlen / float(HLEN))))]))[:mlen]
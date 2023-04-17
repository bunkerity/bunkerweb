<a name="unreleased"></a>
## [Unreleased]


<a name="0.8.21"></a>
## [0.8.21] - 2023-03-24
### features
- **x509.store:** extend verify to support setting flags ([#104](https://github.com/fffonion/lua-resty-openssl/issues/104)) [fa45b6c](https://github.com/fffonion/lua-resty-openssl/commit/fa45b6ce197dee7e2a55601bd4833f415c6cbaa2)


<a name="0.8.20"></a>
## [0.8.20] - 2023-03-10
### bug fixes
- **pkey:** use group bits instead of ECDSA_sig to get parameter size in ECDSA signature ([#102](https://github.com/fffonion/lua-resty-openssl/issues/102)) [f12cbfc](https://github.com/fffonion/lua-resty-openssl/commit/f12cbfc123490c666e2cbd7bec90948910a02336)


<a name="0.8.19"></a>
## [0.8.19] - 2023-03-10
### bug fixes
- **pkey:** fix signature length for secp521r1 ecdsa signature length ([#100](https://github.com/fffonion/lua-resty-openssl/issues/100)) [b7303d4](https://github.com/fffonion/lua-resty-openssl/commit/b7303d49cf738fe134f3e5efbf6157c96ff85237)


<a name="0.8.18"></a>
## [0.8.18] - 2023-03-04
### features
- **bn:** to_binary supports left padding of zeros [d59cac9](https://github.com/fffonion/lua-resty-openssl/commit/d59cac9d7e019e1bcdeaa6714f61294c354cf141)
- **pkey:** allow to convert to and from binary format of ecdsa signature [9a20323](https://github.com/fffonion/lua-resty-openssl/commit/9a203233a23dd08d8f7eeaaff0599921d752a2e2)


<a name="0.8.17"></a>
## [0.8.17] - 2023-01-20
### bug fixes
- **\*:** support OpenSSL 3.1 [dc932f3](https://github.com/fffonion/lua-resty-openssl/commit/dc932f394e5c2b94129b406480897535ec561355)
- **pkey:** allow one shot sign/verify in BoringSSL [32e5df3](https://github.com/fffonion/lua-resty-openssl/commit/32e5df37ac1aaa060c2c1f9b599bd194247d5ecb)


<a name="0.8.16"></a>
## [0.8.16] - 2022-12-20
### features
- **pkey:** load PKCS[#1](https://github.com/fffonion/lua-resty-openssl/issues/1) PEM encoded RSAPublicKey and RSAPrivateKey [3246ec0](https://github.com/fffonion/lua-resty-openssl/commit/3246ec0e51252bfa2812d49f9c6385dcaf0af10b)


<a name="0.8.15"></a>
## [0.8.15] - 2022-10-28
### bug fixes
- **pkey:** check private key existence before doing sign ([#83](https://github.com/fffonion/lua-resty-openssl/issues/83)) [eefcd2a](https://github.com/fffonion/lua-resty-openssl/commit/eefcd2a80b240f44be0bdadd1c2ccc28612004c0)


<a name="0.8.14"></a>
## [0.8.14] - 2022-10-21
### bug fixes
- **x509.crl:** fix metamethods when revoked is empty ([#79](https://github.com/fffonion/lua-resty-openssl/issues/79)) [e65adc7](https://github.com/fffonion/lua-resty-openssl/commit/e65adc7f132628c97e4db69cb5c4b13ff9cf0abf)


<a name="0.8.13"></a>
## [0.8.13] - 2022-10-14
### bug fixes
- **x509.\*:** fix set_extension will fail when a extension with same NID is not exist yet ([#75](https://github.com/fffonion/lua-resty-openssl/issues/75)) [b2f57b8](https://github.com/fffonion/lua-resty-openssl/commit/b2f57b860509a371ab1df71bbbc9e176e5a4d004)

### features
- **x509.altname:** support set and get IP addresses ([#74](https://github.com/fffonion/lua-resty-openssl/issues/74)) [363c80d](https://github.com/fffonion/lua-resty-openssl/commit/363c80d1f2c7ba29dce268e213a9a16c9eae2953)
- **x509.store:** add set_flags ([#77](https://github.com/fffonion/lua-resty-openssl/issues/77)) [8f3f16a](https://github.com/fffonion/lua-resty-openssl/commit/8f3f16a2b6d6c0f680c781f20a9e84a631da9aa5)


<a name="0.8.11"></a>
## [0.8.11] - 2022-10-12
### performance improvements
- **\*:** reuse cdata to improve performance [fc9cecd](https://github.com/fffonion/lua-resty-openssl/commit/fc9cecd785fc0193290cc3398d1ebbe7ae66fe15)


<a name="0.8.10"></a>
## [0.8.10] - 2022-06-24
### features
- **x509:** add get_signature_digest_name [d54b5d6](https://github.com/fffonion/lua-resty-openssl/commit/d54b5d61bc14813121f4a6bda2e1d7eab215094a)


<a name="0.8.9"></a>
## [0.8.9] - 2022-06-23
### bug fixes
- **aux/nginx:** add nginx 1.21.4 and ngx_lua 0.10.21 to support matrix [028da56](https://github.com/fffonion/lua-resty-openssl/commit/028da56d7de606d4b4b323fb3686ad4d93f69c7d)


<a name="0.8.8"></a>
## [0.8.8] - 2022-04-14
### bug fixes
- **ctx:** use global ctx where request is unavailable [e3590cf](https://github.com/fffonion/lua-resty-openssl/commit/e3590cfcbeb6f0d5f110c3c4e1b6cdc63b88e001)
- **x509.extension:** correct X509V3_CTX size for OpenSSL 3.0 [0946c59](https://github.com/fffonion/lua-resty-openssl/commit/0946c5937fa9fa4bb41a70267a67fcc87307b6a6)

### features
- **x509.extension:** add X509V3_set_issuer_pkey in OpenSSL 3.0 [dbd3f74](https://github.com/fffonion/lua-resty-openssl/commit/dbd3f7418a665ae797e6ffc71ba1d7f0660c95f0)
- **x509.store:** add set_purpose and verify_method parameter [b7500fe](https://github.com/fffonion/lua-resty-openssl/commit/b7500fe7212c26070363afeab4a8acfe44c3cfc8)


<a name="0.8.7"></a>
## [0.8.7] - 2022-03-18
### features
- **x509.crl:** add functions to find and inspect revoked list in CRL [37c1661](https://github.com/fffonion/lua-resty-openssl/commit/37c1661fbebebad3b804f602f631e4ba65b80e07)


<a name="0.8.6"></a>
## [0.8.6] - 2022-03-16
### bug fixes
- **obj:** clean up stale error occured from OBJ_txt2* [219a2f0](https://github.com/fffonion/lua-resty-openssl/commit/219a2f0cace8480800394d6e88b188138f2650a1)
- **pkey:** clear_error in passphrase type mismatch [8577422](https://github.com/fffonion/lua-resty-openssl/commit/857742273629d4e801a2d862644213fe5fdbf02a)
- **x509.\*:** move clear_error to last when loading [369eea1](https://github.com/fffonion/lua-resty-openssl/commit/369eea1e4a1a185055296e07f272a3e470442916)

### features
- **openssl:** add function to list SSL ciphers [9861af1](https://github.com/fffonion/lua-resty-openssl/commit/9861af1a074f74f529e341049ada29cbf7d57a48)
- **ssl:** refine various handshake controlling functions [30bf41e](https://github.com/fffonion/lua-resty-openssl/commit/30bf41e958775f60afff1976fe731978c816dd25)


<a name="0.8.5"></a>
## [0.8.5] - 2022-02-02
### bug fixes
- **\*:** correct size type in cipher, hmac and rand in BoringSSL [54ce5f0](https://github.com/fffonion/lua-resty-openssl/commit/54ce5f0dd1861f2af15eacea154c805a237c03d8)
- **bn:** use BN_check_prime in OpenSSL 3.0 [8c107e3](https://github.com/fffonion/lua-resty-openssl/commit/8c107e3dcf2006d6c453234278ab0a45109042d6)
- **kdf:** correct FFI definition for BoringSSL [30ba7cf](https://github.com/fffonion/lua-resty-openssl/commit/30ba7cf9d90d8bc611cbccdca83e69c308739b60)
- **stack:** correct indices to use size_t in BoringSSL [526ecb8](https://github.com/fffonion/lua-resty-openssl/commit/526ecb89c81b0e477b749a2424231329e468ce02)

### features
- **\*:** add more modules for OSSL_LIB_CTX support [35f4bcb](https://github.com/fffonion/lua-resty-openssl/commit/35f4bcb796bc2fbe4ab066b8f78047bf30118986)


<a name="0.8.4"></a>
## [0.8.4] - 2021-12-20
### bug fixes
- **x509.\*:** use SHA256 as default sign digest in BoringSSL [355681a](https://github.com/fffonion/lua-resty-openssl/commit/355681a33d88d85de0faae3e8eb6685e0e3b9f34)

### features
- **pkey:** add pkey:get_default_digest_type [0572e57](https://github.com/fffonion/lua-resty-openssl/commit/0572e57e0ab418f2dd749dbc5042b0c680e346a7)


<a name="0.8.3"></a>
## [0.8.3] - 2021-12-16
### bug fixes
- **hmac:** include evp.md headers [125ea05](https://github.com/fffonion/lua-resty-openssl/commit/125ea059da6b1effef7a187c434ebd6022dc3b82)


<a name="0.8.2"></a>
## [0.8.2] - 2021-11-22
### bug fixes
- **jwk:** fix typo of secp521r1 [81d2a64](https://github.com/fffonion/lua-resty-openssl/commit/81d2a646bde7a66ab87e127eace0d40aa714be58)


<a name="0.8.1"></a>
## [0.8.1] - 2021-11-05
### bug fixes
- **ssl_ctx:** fix typo when getting SSL_CTX from request [7b9e90f](https://github.com/fffonion/lua-resty-openssl/commit/7b9e90faef8337c759c281172be8c1f599be704d)

### features
- **ctx:** add ctx module to provide OSSL_LIB_CTX context [65750bf](https://github.com/fffonion/lua-resty-openssl/commit/65750bfd800b2eebeb9bf653a03518f3ad235fba)


<a name="0.8.0"></a>
## [0.8.0] - 2021-10-29
### bug fixes
- **\*:** move EVP_* definition into seperate files [e0c3d61](https://github.com/fffonion/lua-resty-openssl/commit/e0c3d6178e8b0baab5c53d331dedf8ffb1b1b0c7)
- **auxiliary/nginx:** set off_t to 64bit per nginx config ([#32](https://github.com/fffonion/lua-resty-openssl/issues/32)) [8c209fa](https://github.com/fffonion/lua-resty-openssl/commit/8c209fabbd4ba2f1d6f3a267059c758b4697a433)
- **pkey:** allow sign/verify without md_alg for EdDSA on BoringSSL [ab83fd4](https://github.com/fffonion/lua-resty-openssl/commit/ab83fd4fc053f496699d5dcc77dbb551e2389e77)
- **x509:** compatibility for BoringSSL 1.1.0 (fips-20190808) [84244af](https://github.com/fffonion/lua-resty-openssl/commit/84244af7d91e3421dfccdf1940beb70adbd66adb)

### features
- **evp:** add geneirc function to get and set params [c724e1d](https://github.com/fffonion/lua-resty-openssl/commit/c724e1d41010fab7fb112ca3674eef1aab0b06be)
- **kdf:** add new API with EVP_KDF interfaces [2336ae3](https://github.com/fffonion/lua-resty-openssl/commit/2336ae3b9a7a05473e251a10523a7357afb6f2f2)
- **mac:** add EVP_MAC [0625be9](https://github.com/fffonion/lua-resty-openssl/commit/0625be92e0eaf6a9ee61b3499690d6079aaf933d)
- **openssl:** add function list mac and kdf algorithms and set properties for EVP algorithm fetches [0ed8316](https://github.com/fffonion/lua-resty-openssl/commit/0ed83167dbb1b7d8171bcb59cb749187220572e2)
- **openssl:** support FIPS in OpenSSL 3.0 [beb3ad3](https://github.com/fffonion/lua-resty-openssl/commit/beb3ad3ec8f162aeb11d3f89ea8211c2f3e38c1e)
- **param:** add new function to use OSSL_PARAM [5ffbbcc](https://github.com/fffonion/lua-resty-openssl/commit/5ffbbcce386d98127c84b7f24bb019cff76c05e3)
- **provider:** cipher, digest, kdf, pkey and x509 can now fetch by provider and has new get_provider_name function [52938ca](https://github.com/fffonion/lua-resty-openssl/commit/52938ca5b66f48186815975d685227836bd92cef)


<a name="0.7.5"></a>
## [0.7.5] - 2021-09-18
### bug fixes
- **\*:** rename some EVP_ API to use get in openssl3.0 [8fbdb39](https://github.com/fffonion/lua-resty-openssl/commit/8fbdb396d0a4988a24ff2e0404c1866a416d9cff)
- **aux/nginx:** add 1.19.9 [eb73691](https://github.com/fffonion/lua-resty-openssl/commit/eb73691c058c9d55a1b57405f889f5bc3ecd0420)


<a name="0.7.4"></a>
## [0.7.4] - 2021-08-02
### bug fixes
- **extension:** fallback to ASN1_STRING_print in extension:text where X509V3_EXT_print is not available [f0268f5](https://github.com/fffonion/lua-resty-openssl/commit/f0268f55b124eb4ff65b472899e241af850f9d35)


<a name="0.7.3"></a>
## [0.7.3] - 2021-06-29
### bug fixes
- **pkey:** only pass in passphrase/passphrase_cb to PEM_* functions [6a56494](https://github.com/fffonion/lua-resty-openssl/commit/6a564949e08a6dbe87a44d82e694d862b77c8b68)
- **pkey:** avoid callbacks overflow when setting passphrase_cb [e8aec4e](https://github.com/fffonion/lua-resty-openssl/commit/e8aec4e3ceb4419e373938f9ad4b592efa43acfc)

### features
- **pkey:** allow to specify digest type and padding scheme in sign/verify [ff982ba](https://github.com/fffonion/lua-resty-openssl/commit/ff982ba374ab543c440ccab597d71cdbf4560cdb)


<a name="0.7.2"></a>
## [0.7.2] - 2021-03-25
### bug fixes
- **\*:** redefine callback functions to a style FFI will not overflow [f91202c](https://github.com/fffonion/lua-resty-openssl/commit/f91202c57b826d935d831ec452d2b90fc33277fa)


<a name="0.7.1"></a>
## [0.7.1] - 2021-03-18
### bug fixes
- **altname:** return unsupported as value in not implemented types [ef5e1ed](https://github.com/fffonion/lua-resty-openssl/commit/ef5e1eda9eaea1fd4c8d7d65e438275fed10cdc6)
- **auxiliary/nginx:** typo in error message [4bd22d8](https://github.com/fffonion/lua-resty-openssl/commit/4bd22d81419ed160af1dcea16f42fd284f8f2ad5)


<a name="0.7.0"></a>
## [0.7.0] - 2021-02-19
### bug fixes
- **csr:** count extension count in openssl 3.0 [5af0f4b](https://github.com/fffonion/lua-resty-openssl/commit/5af0f4b02edd0fb8c461a1e08b04eb4eb781f744)
- **csr:** BREAKING: remove csr:set_subject_alt function [513fd8a](https://github.com/fffonion/lua-resty-openssl/commit/513fd8ac61b6f7775465eabc5a3d6a454ccebc54)
- **openssl:** include crypto header in openssl.lua [ef54bf7](https://github.com/fffonion/lua-resty-openssl/commit/ef54bf72710f2613ac6d6e5e8ebb712fa7135939)
- **openssl:** BREAKING: not load sub modules by default [a402f05](https://github.com/fffonion/lua-resty-openssl/commit/a402f05f3ea4b85589c1de6b4347cdfc4c397ea7)

### features
- **\*:** support BoringSSL [9c4e5dc](https://github.com/fffonion/lua-resty-openssl/commit/9c4e5dccefb7fa2e08c489e2922ea05e043e28f2)
- **bn:** add generate_prime [2cc77a4](https://github.com/fffonion/lua-resty-openssl/commit/2cc77a4513dad2f4d684535d1230484e8e91bfbd)
- **openssl:** add function to list supported cipher and digest algorithms [5bdc2a4](https://github.com/fffonion/lua-resty-openssl/commit/5bdc2a406c974f471331636de670915df9386f82)
- **openssl:** add function to get and set fips mode [f6de183](https://github.com/fffonion/lua-resty-openssl/commit/f6de183b19e57616ded39e73518acd198c730056)


<a name="0.6.11"></a>
## [0.6.11] - 2021-01-21
### bug fixes
- **aux/nginx:** only show warning message when function is being called [9964a6d](https://github.com/fffonion/lua-resty-openssl/commit/9964a6d29aded1c0d06c1a8700ee313e08506c2f)
- **openssl:** not load ssl modules by default [390ad79](https://github.com/fffonion/lua-resty-openssl/commit/390ad79c413ec779ff7a1ad2b86ff0fe389c085d)
- **ssl:** add function to free the verify callback function [62dc81a](https://github.com/fffonion/lua-resty-openssl/commit/62dc81a4c7be1c745e7e3ab728f3e060c981f446)


<a name="0.6.10"></a>
## [0.6.10] - 2021-01-12
### bug fixes
- **ecx:** return nil, err in set_parameters [98acaee](https://github.com/fffonion/lua-resty-openssl/commit/98acaeeeaa60dffd93a934f4fbf7ddfd8e9e9652)
- **pkey:** use named_curve encoding for EC group [1e65d9d](https://github.com/fffonion/lua-resty-openssl/commit/1e65d9d4b71c0e9c5f4d404e640a96e03902fd30)

### features
- **pkcs12:** allow to define algorithm to encrypt key and cert [b9678ce](https://github.com/fffonion/lua-resty-openssl/commit/b9678ce4ee4a233fb0bd8ed61d41c6d45a6fbb9d)
- **pkcs12:** check on cert and key mismatch [5953cc2](https://github.com/fffonion/lua-resty-openssl/commit/5953cc281cff06027f3b2bba23402e2915fd3ae1)
- **pkcs12:** encode and decode for pkcs12 [1467579](https://github.com/fffonion/lua-resty-openssl/commit/1467579fbe253996570dd188f580b98b8eb1db98)
- **pkey:** add is_private function to check if it's a private key [eb6cc1c](https://github.com/fffonion/lua-resty-openssl/commit/eb6cc1c2d5f7698c2641950d745a78da7baa6225)
- **ssl:** add the ssl and ssl_ctx module [40f3999](https://github.com/fffonion/lua-resty-openssl/commit/40f39994446a4cb954fc516f7047194cbf1141f8)


<a name="0.6.9"></a>
## [0.6.9] - 2020-11-09
### bug fixes
- **\*:** not mutating tables when doing pairs to avoid missing of iterration [836d5c9](https://github.com/fffonion/lua-resty-openssl/commit/836d5c915b27c0e63782c47effae16515ba71fed)
- **pkey:** fix typo in paramgen error message [d341246](https://github.com/fffonion/lua-resty-openssl/commit/d341246b5db5f912a3bcb06b7be1d08ffee093b3)
- **tests:** openssl3.0 alpha7 [5caa0e6](https://github.com/fffonion/lua-resty-openssl/commit/5caa0e60193ea535d0c0f1fe8491bc6779c9e720)
- **x509.altname:** organize GC handling better [f5a138c](https://github.com/fffonion/lua-resty-openssl/commit/f5a138c8b10dd285d9cacb6f2b3877b7831d0fba)

### features
- **provider:** add the provider module [dff92af](https://github.com/fffonion/lua-resty-openssl/commit/dff92af37102b094f1187914a0c76b6635130626)
- **x509.\*:** add get_signature_nid and get_signature_name [a35ae0a](https://github.com/fffonion/lua-resty-openssl/commit/a35ae0af6ad98251d4226e0daceab07c2832fc17)


<a name="0.6.8"></a>
## [0.6.8] - 2020-10-15
### bug fixes
- **pkey:** correctly free parameter after new parameters are set for RSA and DH keys on OpenSSL 1.0.2 [32d8c12](https://github.com/fffonion/lua-resty-openssl/commit/32d8c127f29e4ee0f13a8191f05f85ec74c2d8d4)
- **tests:** sort json in tests [aeeb7c3](https://github.com/fffonion/lua-resty-openssl/commit/aeeb7c3c2c7899b1b9c36b620476cca81b8eefdc)

### features
- **pkey:** allow to pass params for EC and DH keygen [e9aa7c7](https://github.com/fffonion/lua-resty-openssl/commit/e9aa7c751458134d03dfcda1318186cf3a691c1d)
- **pkey:** get and set DH parameters [ebaad8d](https://github.com/fffonion/lua-resty-openssl/commit/ebaad8d1e6533c9ad4980f557ead986104b947d0)
- **pkey:** support DH key and paramgen [f4661c6](https://github.com/fffonion/lua-resty-openssl/commit/f4661c6eb1d57d36daa93e8c86105b77ba8fe0cb)
- **pkey:** support one shot signing for all key types [79ca0d4](https://github.com/fffonion/lua-resty-openssl/commit/79ca0d43feda10894bfe5f0e72c4460dd4778c66)


<a name="0.6.7"></a>
## [0.6.7] - 2020-10-08
### features
- **pkey:** sign_raw and verify_recover [90ed1b6](https://github.com/fffonion/lua-resty-openssl/commit/90ed1b637729bfde33a94c6467327419186bdd38)


<a name="0.6.6"></a>
## [0.6.6] - 2020-09-29
### bug fixes
- **\*:** export tostring for x509.name and x509.altname [6143659](https://github.com/fffonion/lua-resty-openssl/commit/6143659706ea5b8c42a418b7fac1eae4179a6280)
- **kdf:** fix HKDF potential buffer overflow [da6f420](https://github.com/fffonion/lua-resty-openssl/commit/da6f42025c657f610f1ebee95f0489afd3628d9f)
- **x509.name:** potential memory leak in x509.name:find() [ac51fb1](https://github.com/fffonion/lua-resty-openssl/commit/ac51fb10581ec31e639c1298c080a899466fd57d)
- **x509.store:** return all error on load_file or add failure [a4ee237](https://github.com/fffonion/lua-resty-openssl/commit/a4ee2379802e41f5b5566ac11e59598d1f338ca5)

### features
- **x509.extension:** support create by ASN.1 octet string and nconf [7d8e81f](https://github.com/fffonion/lua-resty-openssl/commit/7d8e81f6789abd951f6e6b3aeb96607f8682c1d5)


<a name="0.6.5"></a>
## [0.6.5] - 2020-09-16
### bug fixes
- **\*:** x509.* set should return true on success [2a09575](https://github.com/fffonion/lua-resty-openssl/commit/2a09575425133e92c990513c7ea7445cf2ca47f4)


<a name="0.6.4"></a>
## [0.6.4] - 2020-08-27
### features
- **x509.csr:** finish {set,add}_extension functions [d34b702](https://github.com/fffonion/lua-resty-openssl/commit/d34b702a17b4f491e2a97e971da1d6125d482066)
- **x509.extension:** add ability to convert to other data type [15a5c7f](https://github.com/fffonion/lua-resty-openssl/commit/15a5c7ff38452a7bd04919b4a7e9c9dc1dfa931d)


<a name="0.6.3"></a>
## [0.6.3] - 2020-08-10
### bug fixes
- **\*:** cleanup and centralize ffi.typeof [5cbc247](https://github.com/fffonion/lua-resty-openssl/commit/5cbc2475bc5926fb0e4aa1b3e5b592144518d013)
- **\*:** remove hack for openssl 3.0 around broken EVP_PKEY_base_id [33181c3](https://github.com/fffonion/lua-resty-openssl/commit/33181c34210fb16c4190e88e1892fb19952420b2)
- **cipher:** use CipherFinal_ex and make test more robust [61fa022](https://github.com/fffonion/lua-resty-openssl/commit/61fa0224fc8dca8a13f9c3ae6904e6cb71c00c6b)
- **openssl:** correctly check error for getting version num ([#6](https://github.com/fffonion/lua-resty-openssl/issues/6)) [6a4b9e6](https://github.com/fffonion/lua-resty-openssl/commit/6a4b9e636714e81d405b934868ef347b3c803674)
- **tests:** pin lua-nginx-module and lua-resty-core [010b37e](https://github.com/fffonion/lua-resty-openssl/commit/010b37eb273da7b96ef39f95a6990357ecf49e49)
- **tests:** make pkey parameter test less flaky [d023edc](https://github.com/fffonion/lua-resty-openssl/commit/d023edcba56e5832b04e2ee0d84195c69a6258d4)
- **x509.\*:** pass correct digest parameter to sign [982ad48](https://github.com/fffonion/lua-resty-openssl/commit/982ad48594444994d5c5b98ba9ca3d139ce96f8c)

### features
- **\*:** support reset for hmac and digest [37ba4b0](https://github.com/fffonion/lua-resty-openssl/commit/37ba4b0f63c60898ee25cfeeeab8b5651c62296e)
- **\*:** initial support for OpenSSL 3.0 [be5dc10](https://github.com/fffonion/lua-resty-openssl/commit/be5dc10c24aabb6697ecb9fe2bd75c8a11e2b2d7)
- **x509.csr:** add get_extension and get_extensions function [638ca46](https://github.com/fffonion/lua-resty-openssl/commit/638ca46ecf1a4fdacac6e24abaea7d19db93c98b)
- **x509.extensions:** finish the stack implementation [f4cf725](https://github.com/fffonion/lua-resty-openssl/commit/f4cf7256e9cce0a280fab46d356ca5fcf3a48b4f)
- **x509.revoked:** add the x509.revoked module [58f0ce1](https://github.com/fffonion/lua-resty-openssl/commit/58f0ce11f2a39cdaabf1c9ba38ea7587adf8f25a)


<a name="0.6.2"></a>
## [0.6.2] - 2020-05-13
### bug fixes
- **\*:** add prefix to all error messages [8f52c25](https://github.com/fffonion/lua-resty-openssl/commit/8f52c2583b87ae0e66e9546f5db03d8fe667cbd4)

### features
- **cipher:** AEAD modes with authentication [fd7471e](https://github.com/fffonion/lua-resty-openssl/commit/fd7471e3a011519df0250681ee1bf82d61b1f154)
- **pkey:** support one shot sign/verify for Ed25519 and Ed448 keys [2565e85](https://github.com/fffonion/lua-resty-openssl/commit/2565e85337325f9cee7d601220120b185a22c430)
- **pkey:** support key derivation for EC, X25519 and X448 keys [0c0d941](https://github.com/fffonion/lua-resty-openssl/commit/0c0d9417711f4c9b513ae02382ea6f9f68f750fd)
- **pkey:** output pkey to DER and JWK format [8da24a5](https://github.com/fffonion/lua-resty-openssl/commit/8da24a5cd9241c09f51c610164dee5daffdd9129)
- **pkey:** load EC key from JWK format [df0c06f](https://github.com/fffonion/lua-resty-openssl/commit/df0c06f1e07be3c6e46d9d2a86005361ad386f83)
- **pkey:** set/get_parameters for EC key [67d54c8](https://github.com/fffonion/lua-resty-openssl/commit/67d54c8dc8555870bbf3fb216b3c636f3d9b220d)
- **pkey:** load RSA key from JWK format [dc118b3](https://github.com/fffonion/lua-resty-openssl/commit/dc118b3aec2a9ff26fc3f615a1569525cbc13dd4)
- **pkey:** add function to set rsa parameter [867fa10](https://github.com/fffonion/lua-resty-openssl/commit/867fa109863a2fd770f26a44b15cbea9d422b5cb)


<a name="0.6.1"></a>
## [0.6.1] - 2020-05-08
### bug fixes
- **x509:** fail soft when CRL is not set [2f2eb5e](https://github.com/fffonion/lua-resty-openssl/commit/2f2eb5edc78e3aa892eb36bd1b091c42ddc64480)


<a name="0.6.0"></a>
## [0.6.0] - 2020-03-11
### features
- **bn:** mathematics, bit shift and comparasion operations [87bf557](https://github.com/fffonion/lua-resty-openssl/commit/87bf5575a3643e11814b9c7be68ec78ce05011fe)
- **kdf:** use give id as type parameter [0e767d0](https://github.com/fffonion/lua-resty-openssl/commit/0e767d006f4561788d826eef82b753093f06ef9e)
- **kdf:** kdf.derive in luaossl compat mode [45788b6](https://github.com/fffonion/lua-resty-openssl/commit/45788b6ea742755b31d6b361950f3ea5d5d24bdf)


<a name="0.6.0-rc.0"></a>
## [0.6.0-rc.0] - 2020-03-02
### features
- **altname:** RFC822 alias to email [37467fc](https://github.com/fffonion/lua-resty-openssl/commit/37467fcf83093d0c99251f43a4cc916d5c934eda)
- **kdf:** add key derivation functions support [d78835e](https://github.com/fffonion/lua-resty-openssl/commit/d78835e861df4b7f79bb0fe5e17a2f19be1e0d3f)


<a name="0.5.4"></a>
## [0.5.4] - 2020-02-27
### bug fixes
- **store:** set X509_V_FLAG_CRL_CHECK flag if a crl is added [88574d5](https://github.com/fffonion/lua-resty-openssl/commit/88574d5ecef0f75a293cd7d23b764d629905e3df)
- **x509.\*:** returns soft error if extension is not found [a0a75aa](https://github.com/fffonion/lua-resty-openssl/commit/a0a75aa2644203e22461aa1dd09ef8672e2ba576)


<a name="0.5.3"></a>
## [0.5.3] - 2020-02-22
### features
- **openssl:** lua-resty-hmac compat [fad844f](https://github.com/fffonion/lua-resty-openssl/commit/fad844f804abe8d73b7d4b7655d562fdb3d84ebf)


<a name="0.5.2"></a>
## [0.5.2] - 2020-02-09
### bug fixes
- **pkey:** decrease copy by 1 when generating key [bcc38e9](https://github.com/fffonion/lua-resty-openssl/commit/bcc38e9fc5e733a8f3f9d09e5eef1e2eb3c15d4d)

### features
- **x509.extension:** allow to create an extension by NID [6d66a2d](https://github.com/fffonion/lua-resty-openssl/commit/6d66a2d9fa7cc36cc2e6c85a78ad2236e525f3b0)


<a name="0.5.1"></a>
## [0.5.1] - 2020-02-04
### bug fixes
- **x509.crl:** fix creating empty crl instance [046ca36](https://github.com/fffonion/lua-resty-openssl/commit/046ca36228f639c191c81a7b84dfedfc523d0340)

### features
- **pkey:** load encrypted PEM key [7fa7a29](https://github.com/fffonion/lua-resty-openssl/commit/7fa7a29882bbcef294f83cd1f66b9960344a0e07)
- **x509.extension:** add tostring() as synonym to text() [87c162d](https://github.com/fffonion/lua-resty-openssl/commit/87c162de9fa7bb3e3930bd760ff7dfece30f1b49)


<a name="0.5.0"></a>
## [0.5.0] - 2020-02-03
### bug fixes
- **\*:** add missing crl.dup function, organize store:add gc handler [6815e5d](https://github.com/fffonion/lua-resty-openssl/commit/6815e5df04fdb77c83b0345f166664759a573962)
- **asn1:** support GENERALIZEDTIME string format [8c7e2d6](https://github.com/fffonion/lua-resty-openssl/commit/8c7e2d67857cb6875cf52fadf43cadf05d8c5c40)
- **error:** return latest error string not earliest in some cases [0b5955d](https://github.com/fffonion/lua-resty-openssl/commit/0b5955d4cb73f3c7d3321ed7384ae862640a6a7f)
- **stack:** protective over first argument [bf455ff](https://github.com/fffonion/lua-resty-openssl/commit/bf455ff310b94b26a3bed513ffc9f308f65691ed)
- **x509:** guard around oscp stack index [1b59b85](https://github.com/fffonion/lua-resty-openssl/commit/1b59b8565b5dee4cb1dd14d22bc24ec04dfbf3d6)
- **x509.store:** correctly save x509 instance references [d8d755f](https://github.com/fffonion/lua-resty-openssl/commit/d8d755f7a281ad09d896a1d78ad9e53f6c028bdc)

### features
- **\*:** add iterater and helpers for stack-like objects [46bb723](https://github.com/fffonion/lua-resty-openssl/commit/46bb7237028a16e67878d8310c25e908ceece009)
- **autogen:** generate tests for x509, csr and crl [1392428](https://github.com/fffonion/lua-resty-openssl/commit/1392428352164d2a1a6e0c03075ff65b55aecdee)
- **objects:** add helper function for ASN1_OBJECT [d037706](https://github.com/fffonion/lua-resty-openssl/commit/d037706c11d716afe3616bdaf4658afc1763081d)
- **pkey:** asymmetric encryption and decryption [6d60451](https://github.com/fffonion/lua-resty-openssl/commit/6d60451157edbf9cefb634f888dfa3e6d9be302f)
- **x509:** getter/setters for extensions [243f40d](https://github.com/fffonion/lua-resty-openssl/commit/243f40d35562a516f404188a5c7eb8f5134d9b30)
- **x509:** add get_ocsp_url and get_crl_url [6141b6f](https://github.com/fffonion/lua-resty-openssl/commit/6141b6f5aed38706b477a71d8c4383bf55da7eee)
- **x509.altname:** support iterate and decode over the stack [083a201](https://github.com/fffonion/lua-resty-openssl/commit/083a201746e02d51f6c5c640ad9bf8c6730ebe0b)
- **x509.crl:** add crl module [242f8cb](https://github.com/fffonion/lua-resty-openssl/commit/242f8cb45d6c2df5918f26540c92a430d42feb5d)
- **x509.csr:** autogen some csr functions as well [9800e36](https://github.com/fffonion/lua-resty-openssl/commit/9800e36c2ff8a299b88f24091cc722940a8652bb)
- **x509.extension:** decode object, set/get critical flag and get text representation [8cb585f](https://github.com/fffonion/lua-resty-openssl/commit/8cb585fc51de04065cd7eeeea06e6240e7251614)
- **x509.extension:** add x509.extension.dist_points and x509.extension.info_access [63d3992](https://github.com/fffonion/lua-resty-openssl/commit/63d3992163144ed75474a8046398d605570c30b7)


<a name="0.4.4"></a>
## [0.4.4] - 2020-02-27
### bug fixes
- **pkey:** clean up errors when trying loading key types [7b3d351](https://github.com/fffonion/lua-resty-openssl/commit/7b3d3513cfb7a8800f49dbdd3ca521b4dadefbad)


<a name="0.4.3"></a>
## [0.4.3] - 2020-01-15
### bug fixes
- **asn1:** support GENERALIZEDTIME string format [cc6326f](https://github.com/fffonion/lua-resty-openssl/commit/cc6326fed1bc53e64042d4742208ed68d7bb42ac)


<a name="0.4.2"></a>
## [0.4.2] - 2020-01-06
### bug fixes
- **bn:** memory leak in bn:to_hex [6718e9e](https://github.com/fffonion/lua-resty-openssl/commit/6718e9e76a8410c78b32e5abf6d06a628fe8dc8b)
- **compat:** refine luaossl compat mode [0d86eb5](https://github.com/fffonion/lua-resty-openssl/commit/0d86eb58848e970408bec7ee9d77102c241c3a5c)
- **openssl:** typo in luaossl_compat [#1](https://github.com/fffonion/lua-resty-openssl/issues/1) [1c3ea60](https://github.com/fffonion/lua-resty-openssl/commit/1c3ea60877d1532eaaddc13ab3be1550c4c5a7f1)
- **x509:** memory leak in x509:set_not_(before|after) [b4a32f8](https://github.com/fffonion/lua-resty-openssl/commit/b4a32f82c33107d2db729caa06aee141b7f9a016)
- **x509:** and missing x509.get_serial_number code [e7d0fb6](https://github.com/fffonion/lua-resty-openssl/commit/e7d0fb6eace77d357d19043b88bb765ec29a5193)
- **x509.csr:** correctly gc extension [ece5be3](https://github.com/fffonion/lua-resty-openssl/commit/ece5be3f517b69563150973e7da6063d5826a9ad)
- **x509.store:** memory leak in store:add [57815dd](https://github.com/fffonion/lua-resty-openssl/commit/57815dd38bbb2e260e8cdf3e8ddac48d6254b8fc)


<a name="0.4.1"></a>
## [0.4.1] - 2019-12-24
### bug fixes
- **x509:** correct X509_add1_ext_i2d include path [b08b312](https://github.com/fffonion/lua-resty-openssl/commit/b08b3123a0fb2770296f04c830414bd38588e8eb)

### features
- **x509:** getters for basic constraints and basic constraints critical [82f5725](https://github.com/fffonion/lua-resty-openssl/commit/82f5725d4738b3bf83fcbf3154fe5979fe8d1af4)


<a name="0.4.0"></a>
## [0.4.0] - 2019-12-20
### bug fixes
- **\*:** always return ok, err if there's no explict return value [3e68167](https://github.com/fffonion/lua-resty-openssl/commit/3e681676f85e26c8c7af6f72a2c4afcb98952cd6)
- **evp:** correct ptr naming [72f8765](https://github.com/fffonion/lua-resty-openssl/commit/72f8765250861d6504a767da81afe19c2d2896a4)

### features
- **\*:** add x509.digest and bn.to_hex [11ea9ae](https://github.com/fffonion/lua-resty-openssl/commit/11ea9aebca6bb5c354ad94525bd2e264debfebbd)
- **version:** add function to print human readable version [7687573](https://github.com/fffonion/lua-resty-openssl/commit/76875731011e5641eef9881ace2becf1bf057cfd)
- **x509:** add x509 stack (chain) support [72154fc](https://github.com/fffonion/lua-resty-openssl/commit/72154fcb7686ce5a754d4fe4f121f07507a1513e)
- **x509.chain:** allow to duplicate a stack [3fa19b7](https://github.com/fffonion/lua-resty-openssl/commit/3fa19b79509c73cf5dce6e3445cbf90a9466d656)
- **x509.name:** allow to iterate over objects and find objects [714a1e5](https://github.com/fffonion/lua-resty-openssl/commit/714a1e541e0ce3ffb33d257d9af50ae628094fb2)
- **x509.store:** support certificate verification [c9dd4bf](https://github.com/fffonion/lua-resty-openssl/commit/c9dd4bf8065a51a97fcf940c33ba046b73ac2049)


<a name="0.3.0"></a>
## [0.3.0] - 2019-12-12
### bug fixes
- **\*:** move cdef and macros to seperate file [28c3390](https://github.com/fffonion/lua-resty-openssl/commit/28c339085383bfbcb72e192701b96e08fb4344f0)
- **\*:** normalize error handling [ff18d54](https://github.com/fffonion/lua-resty-openssl/commit/ff18d54d2b4402de3bc02731f99c32a9953f8784)

### features
- **cipher:** add symmetric cryptography support [9b89e8d](https://github.com/fffonion/lua-resty-openssl/commit/9b89e8dcc1489832c893373150bfeef6a838da34)
- **hmac:** add hmac support [5cc2a15](https://github.com/fffonion/lua-resty-openssl/commit/5cc2a15ce43a9c1c73dccf1a15232ee2a9108460)


<a name="0.2.1"></a>
## [0.2.1] - 2019-10-22
### bug fixes
- **x509:** decrease by set_version by 1 per standard [b6ea5b9](https://github.com/fffonion/lua-resty-openssl/commit/b6ea5b933aadfb8284f7486eb33d8a4c21b7a6de)


<a name="0.2.0"></a>
## 0.2.0 - 2019-10-18
### bug fixes
- **\*:** fix working and name test [f6db7ef](https://github.com/fffonion/lua-resty-openssl/commit/f6db7ef3c1ce5f9a75f01dc24f904fd8942c7897)
- **\*:** normalize naming, explictly control cdef for different openssl versions [c626b53](https://github.com/fffonion/lua-resty-openssl/commit/c626b538c2dc33272b130503ddd21f21bd9d995f)
- **\*:** cleanup cdef [3c02d02](https://github.com/fffonion/lua-resty-openssl/commit/3c02d020822a30fdf7dae0aa7c6aa47c4660aea8)
- **\*:** test cdata type before passing in ffi [de99069](https://github.com/fffonion/lua-resty-openssl/commit/de99069e40c075844a15b91720e2d5c9c9a68dd7)

### features
- **\*:** add more x509 API, and rand bytes generator [6630fde](https://github.com/fffonion/lua-resty-openssl/commit/6630fde2e5e9f367e4652dc390678d4eeb57ad5d)
- **error:** add ability to pull error description [d19ece9](https://github.com/fffonion/lua-resty-openssl/commit/d19ece993ac797fdf6708400cf83e3f4ed0bb9f4)
- **x509:** generate certificate [9b4f59b](https://github.com/fffonion/lua-resty-openssl/commit/9b4f59bf94647aab37da6b8076ee99e155ba8023)
- **x509:** export pubkey [ede4f81](https://github.com/fffonion/lua-resty-openssl/commit/ede4f817cb0fe092ad6f9ab5d6ecdcde864a9fd8)


[Unreleased]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.21...HEAD
[0.8.21]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.20...0.8.21
[0.8.20]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.19...0.8.20
[0.8.19]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.18...0.8.19
[0.8.18]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.17...0.8.18
[0.8.17]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.16...0.8.17
[0.8.16]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.15...0.8.16
[0.8.15]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.14...0.8.15
[0.8.14]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.13...0.8.14
[0.8.13]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.11...0.8.13
[0.8.11]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.10...0.8.11
[0.8.10]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.9...0.8.10
[0.8.9]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.8...0.8.9
[0.8.8]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.7...0.8.8
[0.8.7]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.6...0.8.7
[0.8.6]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.5...0.8.6
[0.8.5]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.4...0.8.5
[0.8.4]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.3...0.8.4
[0.8.3]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.2...0.8.3
[0.8.2]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.1...0.8.2
[0.8.1]: https://github.com/fffonion/lua-resty-openssl/compare/0.8.0...0.8.1
[0.8.0]: https://github.com/fffonion/lua-resty-openssl/compare/0.7.5...0.8.0
[0.7.5]: https://github.com/fffonion/lua-resty-openssl/compare/0.7.4...0.7.5
[0.7.4]: https://github.com/fffonion/lua-resty-openssl/compare/0.7.3...0.7.4
[0.7.3]: https://github.com/fffonion/lua-resty-openssl/compare/0.7.2...0.7.3
[0.7.2]: https://github.com/fffonion/lua-resty-openssl/compare/0.7.1...0.7.2
[0.7.1]: https://github.com/fffonion/lua-resty-openssl/compare/0.7.0...0.7.1
[0.7.0]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.11...0.7.0
[0.6.11]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.10...0.6.11
[0.6.10]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.9...0.6.10
[0.6.9]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.8...0.6.9
[0.6.8]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.7...0.6.8
[0.6.7]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.6...0.6.7
[0.6.6]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.5...0.6.6
[0.6.5]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.4...0.6.5
[0.6.4]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.3...0.6.4
[0.6.3]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.2...0.6.3
[0.6.2]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.1...0.6.2
[0.6.1]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.0...0.6.1
[0.6.0]: https://github.com/fffonion/lua-resty-openssl/compare/0.6.0-rc.0...0.6.0
[0.6.0-rc.0]: https://github.com/fffonion/lua-resty-openssl/compare/0.5.4...0.6.0-rc.0
[0.5.4]: https://github.com/fffonion/lua-resty-openssl/compare/0.5.3...0.5.4
[0.5.3]: https://github.com/fffonion/lua-resty-openssl/compare/0.5.2...0.5.3
[0.5.2]: https://github.com/fffonion/lua-resty-openssl/compare/0.5.1...0.5.2
[0.5.1]: https://github.com/fffonion/lua-resty-openssl/compare/0.5.0...0.5.1
[0.5.0]: https://github.com/fffonion/lua-resty-openssl/compare/0.4.4...0.5.0
[0.4.4]: https://github.com/fffonion/lua-resty-openssl/compare/0.4.3...0.4.4
[0.4.3]: https://github.com/fffonion/lua-resty-openssl/compare/0.4.2...0.4.3
[0.4.2]: https://github.com/fffonion/lua-resty-openssl/compare/0.4.1...0.4.2
[0.4.1]: https://github.com/fffonion/lua-resty-openssl/compare/0.4.0...0.4.1
[0.4.0]: https://github.com/fffonion/lua-resty-openssl/compare/0.3.0...0.4.0
[0.3.0]: https://github.com/fffonion/lua-resty-openssl/compare/0.2.1...0.3.0
[0.2.1]: https://github.com/fffonion/lua-resty-openssl/compare/0.2.0...0.2.1

@rem Generate automatically-generated configuration-independent source files
@rem and build scripts.
@rem Requirements:
@rem * Perl must be on the PATH ("perl" command).
@rem * Python 3.8 or above must be on the PATH ("python" command).
@rem * Either a C compiler called "cc" must be on the PATH, or
@rem   the "CC" environment variable must point to a C compiler.

@rem @@@@ library\** @@@@
@rem psa_crypto_driver_wrappers.h needs to be generated prior to
@rem generate_visualc_files.pl being invoked.
python scripts\generate_driver_wrappers.py || exit /b 1
perl scripts\generate_errors.pl || exit /b 1
perl scripts\generate_query_config.pl || exit /b 1
perl scripts\generate_features.pl || exit /b 1
python framework\scripts\generate_ssl_debug_helpers.py || exit /b 1

@rem @@@@ Build @@@@
perl scripts\generate_visualc_files.pl || exit /b 1

@rem @@@@ programs\** @@@@
python scripts\generate_psa_constants.py || exit /b 1

@rem @@@@ tests\** @@@@
python framework\scripts\generate_bignum_tests.py || exit /b 1
python framework\scripts\generate_config_tests.py || exit /b 1
python framework\scripts\generate_ecp_tests.py || exit /b 1
python framework\scripts\generate_psa_tests.py || exit /b 1
python framework\scripts\generate_test_keys.py --output framework\tests\include\test\test_keys.h || exit /b 1
python framework\scripts\generate_test_cert_macros.py --output tests\src\test_certs.h || exit /b 1
python framework\scripts\generate_tls_handshake_tests.py || exit /b 1
python framework\scripts\generate_tls13_compat_tests.py || exit /b 1

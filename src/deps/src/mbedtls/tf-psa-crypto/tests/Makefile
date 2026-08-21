default:
	@echo "This makefile only supports generating test data and key files."
	@echo "It does not support actually building the test code."
	@echo "The only officially supported build tool is CMake."
	false

include crypto-tests.make

generated_files: $(TF_PSA_CRYPTO_TESTS_GENERATED_DATA_FILES)
generated_files: $(TF_PSA_CRYPTO_TESTS_GENERATED_C_FILES)

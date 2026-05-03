InkMatch API course tests

Run all tests:

python -m unittest discover -s course_tests -v

Run by section:

python -m unittest course_tests.test_integration -v
python -m unittest course_tests.test_load -v
python -m unittest course_tests.test_security -v
python -m unittest course_tests.test_resilience -v
python -m unittest course_tests.test_automated -v

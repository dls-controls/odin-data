#!/bin/bash

# Make a dummy .gcda for any .gcno files without one. This makes coverage report 0% for files that aren't executed.
find . -name "*.gcno" -exec sh -c 'touch -a "${1%.gcno}.gcda"' _ {} \;

# Find all .gcda files and run gcov on them with the output as the current directory
echo "Running gcov on all .gcda files..."
find . -name "*.gcda" -exec gcov -p -o {} ./ \;

# Run remote codecov script to upload - gcov is disabled as we already have the reports
echo "Uploading coverage data..."
bash <(curl -s https://codecov.io/bash) -X gcov

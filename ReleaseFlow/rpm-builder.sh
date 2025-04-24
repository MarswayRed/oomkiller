#!/bin/bash
BUILDBASE=$(realpath $(dirname $0))
REPO_PATH=$(realpath $BUILDBASE/..)

rm -rf $PWD/RPMBUILD/{RPMS,SRPMS,SOURCES}

PYTHON_VERSION=$(python3 --version | awk '{print $2}')

# 检查是否存在 Python 3.10 或更高版本
if [[ "$PYTHON_VERSION" < "3.6" ]]; then
    echo "Error: 需要 Python 3.6 或更高版本"
    exit 1
fi

# 检查 rpmbuild 是否存在
if ! command -v rpmbuild &> /dev/null; then
    echo "Error: rpmbuild 命令不存在"
    exit 1
fi

python3 -m pip install -r $REPO_PATH/requirements.txt
python3 $REPO_PATH/setup.py sdist --formats=gztar --dist-dir $BUILDBASE/RPMBUILD/SOURCES
cp $REPO_PATH/oomkiller.conf $BUILDBASE/RPMBUILD/SOURCES/oomkiller.conf
cp $REPO_PATH/oomkiller.service $BUILDBASE/RPMBUILD/SOURCES/oomkiller.service
rpmbuild -ba --define '_topdir '$(pwd)'/ReleaseFlow/RPMBUILD' $BUILDBASE/RPMBUILD/SPECS/oomkiller.spec


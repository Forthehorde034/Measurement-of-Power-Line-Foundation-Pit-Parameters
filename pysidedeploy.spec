[app]
title = pcdviewer
project_dir = C:/workspace/projects/pcdviewer
input_file = src\main.py
project_file = 
exec_directory = C:/workspace/projects/pcdviewer/build
icon = resources/icons/app.ico

[python]
python_path = C:\workspace\projects\.venv310\Scripts\python.exe
packages = Nuitka==2.7.11

[qt]
modules = Core,Gui,OpenGL,OpenGLWidgets,UiTools,Widgets
plugins = assetimporters,generic,iconengines,imageformats,platforminputcontexts,platforms,styles
qml_files = 

[nuitka]
mode = onefile
extra_args = \
	--onefile \
	--verbose \
	--windows-disable-console \
	--enable-plugin=pyside6 \
	--include-qt-plugins=all \
	--noinclude-qt-translations \
	--include-package=open3d \
	--include-package=numpy \
	--include-data-dir=open3d/resources=resources \
	--include-data-dir=resources=resources \
	--include-data-files=mkl_intel_thread.2.dll,mkl_core.dll,open3d.dll \
	--include-python-dlls \
	--output-dir=build \
	--output-filename=pcdviewer.exe


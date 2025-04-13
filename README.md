# Proof of concept for a Critical Chain Based planner

graphbased-ccpm.py

## Get started with proof of concept

1 Clone repo
2 Create virtual python environment
3 Install required libraries
4 run the script

## Todo

1 - Display resource loading chart
2 - Make buffers a special type of task
3 - Insert buffer into project network
4 - Allow project network to go negative? or at least shift whole network to zero after inserting buffer?
5 - Execution phase
    - Specify index day and capture task remaining time, capture
    - Work out updated starts for all dependent tasks
    - Plot keeping buffers in-place
    - When buffer is consumed push out critical chain
    - fever chart
5 - More control over resource capacity per day? No work weekends?


## How to get started with Python and create a basic script

### Create a directory for script

`mkdir ccpm-proof-of-concept`
`cd ccpm-proof-of-concept`

### Create virtual environment for python (Note! veriosn of python installed by uv do not include Tkinter which is required by Matplotlib)
`C:\Python313\python.exe -m venv .venv`

## Activate Python environment
`.\.venv\Scripts\activate.ps1`

## Update pip
`.\.venv\Scripts\python -m pip install --upgrade pip`

## Install required libraries

`.\.venv\Scripts\python -m pip install -r .\requirements.txt`

## Add gitignore

https://raw.githubusercontent.com/github/gitignore/refs/heads/main/Python.gitignore

## Create Git Repo

`git init`
`git add .`
`git commit -m "first commit"`

## Setup github repo

`gh repo create`

## Rename local branch master to main

git branch -m master main
git fetch origin
git branch -u origin/main main
git remote set-head origin -a
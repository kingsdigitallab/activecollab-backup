FROM gitpod/workspace-full
ENV PYTHONUSERBASE=/workspace/.pyenv_mirror/user/current
ENV PATH=$PYTHONUSERBASE/bin:$PATH
ENV PIP_USER=yes
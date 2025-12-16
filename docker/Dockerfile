FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc make git wget curl ca-certificates sudo build-essential python3 python3-pip pkg-config meson ninja-build cmake file binutils xz-utils unzip zlib1g-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 https://github.com/radareorg/radare2 \
  && cd radare2 \
  && chmod +x sys/install.sh \
  && sys/install.sh

RUN useradd -m -s /bin/bash op \
  && mkdir -p /workspace \
  && chown -R op:op /workspace

RUN mkdir -p /home/op/.local/share/opencode \
  && chown -R op:op /home/op/.local

ENV HOME="/home/op"
ENV PATH="/home/op/.opencode/bin:/home/op/.local/bin:/usr/local/bin:${PATH}"

WORKDIR /workspace
VOLUME ["/workspace"]

USER op
ARG R2PM_CORE_PACKAGES="r2mcp r2ghidra decai r2ghidra-sleigh"

RUN r2pm -U
RUN r2pm -ci r2mcp r2ghidra decai r2ghidra-sleigh

RUN curl -fsSL https://opencode.ai/install | bash

RUN mkdir -p /home/op/.config/opencode
COPY --chown=op:op docker/opencode.json /home/op/.config/opencode/opencode.json

COPY --chown=op:op agents/analyze.task.md /opt/prompt_agent.md

USER root
COPY docker/run_analysis.sh /usr/local/bin/run_analysis.sh
RUN chmod +x /usr/local/bin/run_analysis.sh \
  && chown op:op /usr/local/bin/run_analysis.sh

USER op
ENTRYPOINT ["/usr/local/bin/run_analysis.sh"]



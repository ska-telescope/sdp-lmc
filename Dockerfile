FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.10 AS buildenv
FROM artefact.skao.int/ska-tango-images-pytango-runtime:9.3.10 AS runtime

USER root
RUN pip install -r requirements.txt
RUN pip install .

USER tango
ENTRYPOINT ["SDPMaster"]
CMD ["1", "-v4"]

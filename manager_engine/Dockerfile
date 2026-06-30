# Build argument for environment
ARG ENV=production

# Use environment-specific base image
FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    iputils-ping \
    ldap-utils \
    && rm -rf /var/lib/apt/lists/*

#FROM  pstore.artifactory.cec.lab.emc.com/centos:centos7.9.2009
#WORKDIR /app

#RUN sed -i 's/^#baseurl=http/baseurl=https/' /etc/yum.repos.d/*.repo && \
#    sed -i 's/^mirrorlist/#mirrorlist/' /etc/yum.repos.d/*.repo && \
#    sed -i 's/mirror.centos.org/vault.centos.org/' /etc/yum.repos.d/*.repo && \
#    echo "sslverify=false" >> /etc/yum.conf

#RUN yum -y install openssh openssh-server openssh-clients openssl-libs ; \
#yum update -y && \
#    yum install -y openssl && \
#    yum clean all; \
#yum -y install sshpass ; \
#yum -y install epel-release ; \
#yum -y install git git-lfs gcc zlib-devel bzip2-devel readline-devel sqlite-devel ; \
#yum -y install openssl-devel mod_ssl openssl ; \
#yum -y install ipmitool ; \
#yum -y install net-snmp net-snmp-utils net-snmp-python net-snmp-devel ; \
#yum -y install openldap-devel openldap-clients ; \
#yum -y install which ; \
#yum -y install ftp ; \
#yum -y install expect ; \
#yum -y install wget ; \
#yum -y install nfs-utils ; \
#yum install -y patch; \
#yum -y install pkgconfig; \
#yum -y install libXext libXrender libXtst libXi freetype; \
#yum -y install -y libpng-devel; \
#yum -y install -y libffi; \
#yum -y install -y libffi-devel; \
#yum -y install freetype-devel; \
#yum -y install yum install postgresql-devel; \
#yum -y install gcc-c++ ; \
#yum update -y nss curl libcurl ; \
#yum update -y rsyslog ; \
#yum install -y sudo ; \
#yum install -y yum-utils device-mapper-persistent-data lvm2 ; \
#yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo ; \
#yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin ; \
#export CPATH=/usr/include/freetype2:/usr/include/png; \
#export LDFLAGS="-L/usr/lib/x86_64-linux-gnu";


#COPY ./CA-DOCKER/ /etc/pki/ca-trust/source/
#RUN  update-ca-trust


# Set the working directory in the container
WORKDIR /app

# Set environment variable for build
ENV ENV=${ENV}

# Copy the requirements file into the container at /app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN if [ "$ENV" = "development" ]; then \
    pip install --no-cache-dir -r requirements.txt; \
    else \
    pip install --trusted-host pstore.artifactory.cec.lab.emc.com --no-cache-dir -r requirements.txt; \
    fi

# Copy the current directory contents into the container at /app
COPY . /app

# Make port 5000 available to the world outside this container
EXPOSE 5002
ENV FLASK_APP=app.py
ENV FLASK_RUN_PORT=5002
ENV PYTHONHTTPSVERIFY=0

# Define environment variable
#ENV FLASK_APP=app.py

# Run Flask when the container launches
CMD ["flask", "run", "--host=0.0.0.0", "--port=5002"]

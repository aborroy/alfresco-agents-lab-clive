# --- Global ARGs (visible in any FROM) ---------------------------------------
ARG ALFRESCO_IMAGE=alfresco/alfresco-content-repository-community
ARG ALFRESCO_TAG=25.2.0   # sensible default; can be overridden by --build-arg or compose

# ---- Builder stage: compile alfresco-markdown-rendition ----------------------
FROM maven:3.9-eclipse-temurin-17 AS builder

# Optionally pin a ref (tag/branch/commit). Defaults to main.
ARG MDR_GIT_REF=main

# Get source and build (tests skipped for faster image builds)
RUN --mount=type=cache,target=/root/.m2 \
    git clone --depth 1 --branch "${MDR_GIT_REF}" \
      https://github.com/aborroy/alfresco-markdown-rendition.git /src
WORKDIR /src
RUN mvn -B -DskipTests package

# ---- Runtime stage: Alfresco Repository with the add-on installed -----------
FROM ${ALFRESCO_IMAGE}:${ALFRESCO_TAG}

ARG TOMCAT_DIR=/usr/local/tomcat
ARG IMAGEUSERNAME=alfresco

# default user is alfresco (added on the base image alfresco/alfresco-content-repository-community)
# change to root user to be able to install the addons and packages
USER root

# Fix centos mirrors for Alfresco 6.x
RUN sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-* || true && \
    sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-* || true

# Install modules and addons
RUN mkdir -p $TOMCAT_DIR/amps
COPY modules/amps $TOMCAT_DIR/amps
COPY modules/jars $TOMCAT_DIR/webapps/alfresco/WEB-INF/lib

RUN java -jar $TOMCAT_DIR/alfresco-mmt/alfresco-mmt*.jar install \
    $TOMCAT_DIR/amps $TOMCAT_DIR/webapps/alfresco -directory -nobackup -force

# Copy the built JAR from the builder stage into Alfresco's deployment folder
# JAR ends up in /src/target/*.jar after mvn package
COPY --from=builder /src/target/*.jar ${TOMCAT_DIR}/webapps/alfresco/WEB-INF/lib/

# DATABASE
ARG DB
ENV DB $DB

RUN ls -la /etc/yum.repos.d/ && \
    ((sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-* && \
    sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-* 2>/dev/null) || \
    (sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/rocky-* && \
    sed -i 's|#baseurl=http://dl.rockylinux.org/$contentdir|baseurl=http://dl.rockylinux.org/$contentdir|g' /etc/yum.repos.d/rocky-*)) || \
    (dnf clean all && dnf makecache && dnf update -y)

# Install mysql JDBC driver
RUN if [ "$DB" == "mariadb" ] ; then \
    set -x \
        && yum clean all \
        && yum install -y wget \
        && yum clean all \
        && wget -P /tmp/ https://repo1.maven.org/maven2/org/mariadb/jdbc/mariadb-java-client/2.7.4/mariadb-java-client-2.7.4.jar \
        && cp /tmp/mariadb-java-client-2.7.4.jar $TOMCAT_DIR/lib/ \
        && rm -rf /tmp/mariadb-java-client-2.7.4.jar; \
fi



# COMMS
ARG SOLR_COMMS
ENV SOLR_COMMS $SOLR_COMMS

# SSL
ARG TRUSTSTORE_TYPE
ARG TRUSTSTORE_PASS
ARG KEYSTORE_TYPE
ARG KEYSTORE_PASS
ARG CERT_ALIAS

ENV TRUSTSTORE_TYPE=$TRUSTSTORE_TYPE \
    TRUSTSTORE_PASS=$TRUSTSTORE_PASS \
    KEYSTORE_TYPE=$KEYSTORE_TYPE \
    KEYSTORE_PASS=$KEYSTORE_PASS \
    CERT_ALIAS=$CERT_ALIAS

# Enable SSL by adding the proper Connector to server.xml
RUN if [ "$SOLR_COMMS" == "https" ] ; then \
      sed -i "s/\
[[:space:]]\+<\/Engine>/\n\
        <\/Engine>\n\
        <Connector port=\"8443\" protocol=\"org.apache.coyote.http11.Http11NioProtocol\"\n\
            connectionTimeout=\"20000\" maxThreads=\"150\"\n\
            SSLEnabled=\"true\" scheme=\"https\" secure=\"true\"\n\
            defaultSSLHostConfigName=\"localhost\">\n\
                <SSLHostConfig hostName=\"localhost\" protocols=\"TLSv1.3\"\n\
                    certificateVerification=\"required\"\n\
                    truststoreFile=\"\/usr\/local\/tomcat\/keystore\/ssl.truststore\"\n\
                    truststorePassword=\"${TRUSTSTORE_PASS}\" truststoreType=\"${TRUSTSTORE_TYPE}\">\n\
                    <Certificate certificateKeystoreFile=\"\/usr\/local\/tomcat\/keystore\/ssl.keystore\"\n\
                       certificateKeyAlias=\"${CERT_ALIAS}\" type=\"RSA\"\n\
                       certificateKeystorePassword=\"${KEYSTORE_PASS}\" certificateKeystoreType=\"${KEYSTORE_TYPE}\"\/>\n\
                <\/SSLHostConfig>\n\
        <\/Connector>/g" ${TOMCAT_DIR}/conf/server.xml; \
    fi







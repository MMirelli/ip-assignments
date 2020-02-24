from twisted.internet.ssl import optionsForClientTLS, Certificate

# request related info
SIZE = 4096
PORT = 8822
AUTHORITY = u'example.localhost'


def compute_tls_options():
    '''
    Returns TLS connection options.
    '''
    # tls 
    cert_path = '../cert/example.crt'
    cert_data = open(cert_path).read()
    certificate = Certificate.loadPEM(cert_data)

    return optionsForClientTLS(
        hostname=AUTHORITY,
        acceptableProtocols=[b'h2'],
        trustRoot=certificate,
    )


def get_host():
    return AUTHORITY.split('.')[-1]

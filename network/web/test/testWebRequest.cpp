#include "minorGems/network/web/WebRequest.h"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>

int main( int argc, char **argv ) {
    if( argc != 6 ) return 2;
    WebRequest request( "GET", argv[1], NULL, NULL, 3, std::atoi( argv[2] ) );
    int result = 0;
    const auto deadline = std::chrono::steady_clock::now() +
        std::chrono::seconds( 4 );
    while( result == 0 && std::chrono::steady_clock::now() < deadline ) {
        result = request.step();
        if( result == 0 )
            std::this_thread::sleep_for( std::chrono::milliseconds( 1 ) );
    }
    if( result != std::atoi( argv[3] ) ) {
        std::fprintf( stderr, "Unexpected request result: %d\n", result );
        return 1;
    }
    if( result == 1 ) {
        int length = 0;
        unsigned char *body = request.getResult( &length );
        delete [] body;
        if( request.getHTTPStatusCode() != std::atoi( argv[4] ) ||
            length != std::atoi( argv[5] ) ) {
            std::fprintf( stderr, "Unexpected HTTP status/body length: %d/%d\n",
                request.getHTTPStatusCode(), length );
            return 1;
        }
    }
    return 0;
}

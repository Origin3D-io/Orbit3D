#include "orbit3d/wire.hpp"

#include <cassert>
#include <cstdint>
#include <iostream>

int main() {
    orbit3d::wire::Encoder encoder;
    encoder.u8(7);
    encoder.u16(513);
    encoder.u32(0x12345678U);
    encoder.u64(0x0102030405060708ULL);
    encoder.i32(-42);
    encoder.text("Orbit3D");

    orbit3d::wire::Decoder decoder(encoder.bytes());
    assert(decoder.u8() == 7);
    assert(decoder.u16() == 513);
    assert(decoder.u32() == 0x12345678U);
    assert(decoder.u64() == 0x0102030405060708ULL);
    assert(decoder.i32() == -42);
    assert(decoder.text() == "Orbit3D");
    assert(decoder.empty());

    const orbit3d::wire::Header expected{
        orbit3d::wire::MessageType::motion_event,
        36,
        17,
    };
    const auto decoded = orbit3d::wire::decode_header(orbit3d::wire::encode_header(expected));
    assert(decoded.type == expected.type);
    assert(decoded.payload_size == expected.payload_size);
    assert(decoded.request_id == expected.request_id);

    auto incompatible = orbit3d::wire::encode_header(expected);
    incompatible[5] ^= 1;
    try {
        orbit3d::wire::decode_header(incompatible);
        assert(false && "Minor version mismatch must be rejected");
    } catch (const std::runtime_error &error) {
        assert(std::string(error.what()) == "Unsupported Orbit3D protocol version");
    }

    std::cout << "wire test passed\n";
    return 0;
}

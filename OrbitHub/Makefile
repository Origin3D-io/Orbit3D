CXX ?= c++
CC ?= cc
AR ?= ar
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror -pthread
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Wpedantic -Werror
CPPFLAGS ?= -Iinclude -Isrc -DORBIT3D_STATIC
BUILD := build
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
LDLIBS += -ldl
endif

.PHONY: all clean test

all: $(BUILD)/orbithub $(BUILD)/liborbit3d_sdk.a $(BUILD)/orbit3d_sdk_smoke $(BUILD)/orbit3d_c_sdk_smoke $(BUILD)/orbit3d_wire_test

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/wire.o: src/wire.cpp include/orbit3d/wire.hpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@

$(BUILD)/sdk.o: src/sdk.cpp include/orbit3d/orbit3d.h include/orbit3d/wire.hpp src/protocol_io.hpp src/socket.hpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@

$(BUILD)/liborbit3d_sdk.a: $(BUILD)/sdk.o $(BUILD)/wire.o
	$(AR) rcs $@ $^

$(BUILD)/adapter.o: src/adapter.cpp src/adapter.hpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@

$(BUILD)/simulator_adapter.o: src/simulator_adapter.cpp src/simulator_adapter.hpp src/adapter.hpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@

ADAPTER_OBJECTS := $(BUILD)/adapter.o $(BUILD)/simulator_adapter.o

$(BUILD)/orbithub: src/main.cpp src/server.cpp src/protocol_io.hpp src/socket.hpp include/orbit3d/wire.hpp $(BUILD)/wire.o $(ADAPTER_OBJECTS) | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) src/main.cpp src/server.cpp $(BUILD)/wire.o $(ADAPTER_OBJECTS) $(LDLIBS) -o $@

$(BUILD)/orbit3d_sdk_smoke: tests/sdk_smoke.cpp $(BUILD)/liborbit3d_sdk.a | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(BUILD)/liborbit3d_sdk.a -o $@

$(BUILD)/c_sdk_smoke.o: tests/c_sdk_smoke.c include/orbit3d/orbit3d.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(BUILD)/orbit3d_c_sdk_smoke: $(BUILD)/c_sdk_smoke.o $(BUILD)/liborbit3d_sdk.a | $(BUILD)
	$(CXX) $(CXXFLAGS) $^ -o $@

$(BUILD)/orbit3d_wire_test: tests/wire_test.cpp $(BUILD)/wire.o | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(BUILD)/wire.o -o $@

$(BUILD)/orbit3d_sdk_deadline_test: tests/sdk_deadline_test.cpp $(BUILD)/liborbit3d_sdk.a | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(BUILD)/liborbit3d_sdk.a -o $@

test: all $(BUILD)/orbit3d_sdk_deadline_test
	$(BUILD)/orbit3d_sdk_deadline_test
	$(BUILD)/orbit3d_wire_test
	PYTHONPATH=sdk/python/src python3 -m unittest discover -s tests -p 'test_*.py' -v

clean:
	rm -rf $(BUILD)

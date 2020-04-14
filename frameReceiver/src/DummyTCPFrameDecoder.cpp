/*
 * DummyTCPFrameDecoder.cpp
 * 
 */

#include <sstream>

#include "DummyTCPFrameDecoder.h"
#include "version.h"
#include "gettime.h"

using namespace FrameReceiver;

#include "FrameDecoderTCP.h"

namespace FrameReceiver
{

DummyTCPFrameDecoder::DummyTCPFrameDecoder() :
  FrameDecoderTCP(),
  current_frame_number_(-1),
  current_frame_buffer_id_(-1)
{

  current_raw_buffer_.reset(new uint8_t[30]); // Use biggest frame size possible             
  dropped_frame_buffer_.reset(new uint8_t[30]); // Use biggest frame size possible

  this->logger_ = Logger::getLogger("FR.DummyTCPFrameDecoder");
  LOG4CXX_INFO(logger_, "DummyFrameDecoderTCP version " << this->get_version_long() << " loaded");

}

//! Destructor for DummyTCPFrameDecoder
DummyTCPFrameDecoder::~DummyTCPFrameDecoder()
{
}

void* DummyTCPFrameDecoder::get_next_message_buffer(void) {  
  LOG4CXX_INFO(logger_, "get_next_message_buffer_ ");  
  return current_raw_buffer_.get();
}

FrameDecoder::FrameReceiveState DummyTCPFrameDecoder::process_message(size_t bytes_received) {

  return FrameDecoder::FrameReceiveStateComplete;

}

const size_t DummyTCPFrameDecoder::get_frame_buffer_size(void) const {

  return 30;

}

const size_t DummyTCPFrameDecoder::get_frame_header_size(void) const {
 
  return 0;

}

void DummyTCPFrameDecoder::monitor_buffers(void) {

}

void DummyTCPFrameDecoder::get_status(const std::string param_prefix, OdinData::IpcMessage& status_msg) {

}

int DummyTCPFrameDecoder::get_version_major()
{
  return ODIN_DATA_VERSION_MAJOR;
}

int DummyTCPFrameDecoder::get_version_minor()
{
  return ODIN_DATA_VERSION_MINOR;
}

int DummyTCPFrameDecoder::get_version_patch()
{
  return ODIN_DATA_VERSION_PATCH;
}

std::string DummyTCPFrameDecoder::get_version_short()
{
  return ODIN_DATA_VERSION_STR_SHORT;
}

std::string DummyTCPFrameDecoder::get_version_long()
{
  return ODIN_DATA_VERSION_STR;
}

} // namespace FrameReceiver

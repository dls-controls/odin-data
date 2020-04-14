/*
 * DummyTCPFrameDecoder.h
 *
 */

#ifndef INCLUDE_DUMMYTCPFRAMEDECODER_H_
#define INCLUDE_DUMMYTCPFRAMEDECODER_H_

#include "FrameDecoderTCP.h"

namespace FrameReceiver
{

class DummyTCPFrameDecoder : public FrameDecoderTCP
{
public:

  DummyTCPFrameDecoder();

  virtual ~DummyTCPFrameDecoder();

  virtual void* get_next_message_buffer(void);

  virtual void monitor_buffers(void);
  virtual void get_status(const std::string param_prefix, OdinData::IpcMessage& status_msg);

  virtual const size_t get_frame_buffer_size(void) const;
  virtual const size_t get_frame_header_size(void) const;

  int get_version_major();
  int get_version_minor();
  int get_version_patch();
  std::string get_version_short();
  std::string get_version_long();

  virtual FrameReceiveState process_message(size_t bytes_received);

  int current_frame_number_;                                                                                           
  int current_frame_buffer_id_;   

};

} // namespace FrameReceiver
#endif 

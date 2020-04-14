/*
 * DummyTCPFrameDecoderLib.cpp
 *
 */

#include "DummyTCPFrameDecoder.h"
#include "ClassLoader.h"

namespace FrameReceiver
{
  /**
   * Registration of this decoder through the ClassLoader.  This macro
   * registers the class without needing to worry about name mangling
   */
  REGISTER(FrameDecoder, DummyTCPFrameDecoder, "DummyTCPFrameDecoder");

}
// namespace FrameReceiver

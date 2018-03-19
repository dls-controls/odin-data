/*
 * FrameProcessorDefinitions.h
 *
 *  Created on: 31 Oct 2017
 *      Author: vtu42223
 */

#ifndef FRAMEPROCESSOR_FrameProcessorDefinitions_H_
#define FRAMEPROCESSOR_FrameProcessorDefinitions_H_

namespace FrameProcessor
{
  /**
   * Enumeration to store the pixel type of the incoming image
   */
  enum PixelType { pixel_raw_8bit, pixel_raw_16bit, pixel_float32, pixel_raw_64bit };
  /**
   * Enumeration to store the compression type of the incoming image
   */
  enum CompressionType { no_compression, lz4, bslz4, blosc };
  /**
   * Enumeration to store the compression type of the incoming image
   */
  enum ProcessFrameStatus { status_ok, status_complete, status_complete_missing_frames, status_invalid };

  /**
   * Defines a dataset to be saved in HDF5 format.
   */
  struct DatasetDefinition
  {
    /** Name of the dataset **/
    std::string name;
    /** Data type for the dataset **/
    PixelType pixel;
    /** Numer of frames expected to capture **/
    size_t num_frames;
    /** Array of dimensions of the dataset **/
    std::vector<long long unsigned int> frame_dimensions;
    /** Array of chunking dimensions of the dataset **/
    std::vector<long long unsigned int> chunks;
    /** Compression state of data **/
    CompressionType compression;
  };

} /* namespace FrameProcessor */

#endif /* FRAMEPROCESSOR_FrameProcessorDefinitions_H_ */

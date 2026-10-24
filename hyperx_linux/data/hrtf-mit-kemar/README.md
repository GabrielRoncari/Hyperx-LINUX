# MIT KEMAR head-related impulse responses

Taken from the MIT KEMAR measurements ("normal pinna"), SOFA conversion by Piotr Majdak and Michael
Mihocic (Acoustics Research Institute, OeAW), 2020-03-24, from https://sofacoustics.org/data/database/mit/.

Licence, as stated in the data file: "This HRTF data is provided without any usage restrictions. It is
requested that you cite Gardner and Martin (1995) when using this data for research or commercial
applications."

Gardner, W. G., and Martin, K. D. (1995). "HRTF measurements of a KEMAR," J. Acoust. Soc. Am. 97,
3907-3908. Original data: http://sound.media.mit.edu/resources/KEMAR.html

Each file is the left/right impulse response (512 samples, 44.1 kHz, 24-bit, one common gain) for one
direction: `e<elevation>_a<azimuth>.wav`, azimuth 0 = front and 90 = left, as PipeWire's spatializer
counts. Regenerate them from the SOFA file with `python3 -m tools.hrir_extract` (see its header).

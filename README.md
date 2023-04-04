# Semantic-Segmentation-for-Aerial-Images

In this paper, we investigate the problem of Semantic Segmentation for agricultural aerial imagery. This is due to the fact that methods normally applied for semantic segmentation are designed without considering two characteristics of  the aerial data: (i) 
the top-down perspective implies that images lack depth; (ii) there can be a strong  imbalance in the distribution of semantic classes because 
the relevant objects of the scene may appear at extremely different scales (for example, an object only account for 10% of the photo while the other 90% is background).
We propose a solution to these problems based on two ideas: (i) we use together a set of suitable augmentation and a 
consistency loss to guide the model to learn semantic representations that are invariant to the photometric and geometric 
shifts typical of the top-down perspective (Augmentation Invariance); (ii) we use a sampling method (Adaptive Sampling)
that select the training images based on a measure of pixel-wise distribution of classes and actual network confidence. 

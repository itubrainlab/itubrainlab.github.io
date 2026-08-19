---
title: Thesis Project Ideas
sidebar: none
---

Most of the projects in the brAIn lab fall into three (non-exclusive) categories: **experiment**, **data analysis** and **computational modelling**.  
You might, for example, study a specific **computer game** using our lab equipment, or develop some **novel machine-learning** model to be able to tackle some specific brain mechanisms and signals.  
If you are interested in **software development,** the lab is also developing a framework for multi-modal data collection, storage and analysis.

The remainder of this page contains a few ideas for potential Master’s and Bachelor’s theses in the lab. If you are interested in these topics, please do not hesitate to contact us. You can find our email on the [Paople](#/people) page.

## Cognition and Deep Learning

- **Explainable reppresentation learning of the brain activity**: use deep learning and explainable AI methods to investigate brain activity and identify emerging complex patterns.
- **EEG disentanglement**: learn disentangled representations that separate subject-specific, task-specific and noise components of the EEG signal.
- **Privacy and synthesis of biometric data**: study re-identification risks in brain and body signals and explore anonymisation and privacy-preserving learning techniques.
- **EEG foundation models**: investigate large-scale self-supervised pre-training on EEG corpora and transfer across datasets, subjects and tasks.

## Human-AI Interaction

- **Small Language Models for real-time interactive agents**: work with small scale specialised language models to create smart agents in video games.
- **Programming with AI**: investigate the cognitive impact of agentic programming, prompt egineering and other AI innovations in software development.
- **Recoving from AI disasters**: what happens when the AI fails and we need to take over? explore how estreme automation affects human skills and how to design AI based systems that support a healty and safe human-AI interaction.

## Affective Computing and BCI

- **BCI**: explore and experiment with passive and active brain computer interfaces for natural interaction.
- **User and Player Modelling**: develop models to analyse and predic the user experience of players during their interaction in video games.

<!-- ## Investigate the application of deep learning to encode psychophysiological signals (e.g. EEG, Gaze, Blood Pulse) and model human brain behaviour.

- **Stable spatial representation inference in EEG signal**  
  Using neural networks, we can potentially infer the latent structure of the signal, allowing us to use the trained model to understand details about the human brain. Turning this into a reliable method of analysing EEG signals would be a huge development in the field! Several problems remain, though; to begin with, the learned representation is unstable over different model initialisations, which is critical to make the method reliable. We must develop ways to converge the model on the stable representation given the same dataset.
- **Raw EEG transformer**  
  Transformer models have, through the powerful attention mechanism, shown themselves to be strong models of sequences. They are, however, mainly optimised for discrete events (typically nodes), whereas EEG comes in the form of continuous data. Therefore, applying the transformer architecture to raw EEG is still an open challenge. The goal of this project is to investigate the optimal signal representation and tokenisation for raw EEG signals.
- **Explainable EEG transformer**
  Transformers are excellent models of word sequences. Recently, we have seen them be used on EEG data with reasonable performance. With some clever engineering, we can make the models much more explainable, allowing us to understand the important features of the EEG signal. This is an incredibly important development if neuroscientists want to use deep learning models to answer scientific questions about the brain. Can we leverage this technique to explain some cognitive phenomena?
- **EEG private autoencoder for individual cognitive modelling**  
  EEG signals from different people can look very different, mainly because our brains work in different ways. Learning a good shared representation across people would help the analysis of EEG signals greatly, and we think a private encoding layer would solve this problem. The dataset and/or model to be worked on here is undecided.
- **EEG transfer learning**  
  A big problem in using deep learning on EEG data is the access to large amounts of training data, a small lab is simply not able to collect the massive amounts of data needed to train complex models. In other areas of deep learning (like computer vision and language models) transfer learning and fine-tuning are commonly used techniques. Is it possible to do the same with EEG? That is, can we take some large existing datasets and learn the general structure of EEG signals, and then transfer that knowledge to a smaller dataset and increase performance?
- **MoviEEG**  
  There is a big need in neuroscience for larger EEG datasets with well-structured inputs. However, EEG experiments can be boring and straining, making them difficult to complete for longer than an hour at a time. What if we could turn the not-so-great lab experience into a nice movie night? Then an experiment could easily last 2 hours! What we need is a couple of movies that are well-labelled, with cuts and scene descriptions and dialogue. Then we can simply play the movie and create a highly needed dataset meanwhile!

## Computational Models of Player Experience.

- Can we detect and qualify different **players’ emotions** and **cognitive** states while they are playing?
- Can we **adapt the gameplay**? Can we **generate new content** driven by the experience? (generative AI in games)
- **GamEEG**
  There is a big need in neuroscience for larger EEG datasets with well-structured inputs. However, EEG experiments can be boring and straining, making them difficult to complete for longer than an hour at a time. What if we could turn the not-so-great lab experience into a gaming session? Then an experiment could easily last 2 hours! We would need to develop our own games or use some open-source games, so we can record every event happening in the game. Then we can ask people to come and play some games and record their brain activity, meanwhile, creating a highly needed dataset!
- How can **confusion** be leveraged to **prevent boredom** in a game or learning situation?
- How can theories from **learning and education** be used in games to gain insight into the learning experience of playing a game?
- What strategies can be applied to **prevent frustration and boredom** in player experience?
- Dynamically adapting games to control **confusion**.
- **Game tests** focused on engagement, confusion, frustration, and boredom.

## Multimodal Affective Computing

- *The Multimodal Emotion Recognition: Adding Speech and Text to the Pipeline*  
  Advancing Face-to-Face Emotion Communication: A Multimodal Dataset (AFFEC) introduced dual-labelled multimodal signals, while Modelling Emotions in Face-to-Face Setting: The Interplay of Eye-Tracking, Personality, and Temporal Dynamics and MuMTAffect showed how to fuse them. Yet, speech and dialogue remain underused.
- *The Multimodal Emotion Recognition: Better Fusion Strategies*  
  Fusion is a bottleneck in multimodal affective computing. Existing work (MuMTAffect, 2025) tested baseline fusion; this project expands with tensor fusion, adaptive gating, and modality-dropout robustness.
- *The Multimodal Emotion Recognition: Predict Personality for Unknown Users*  
  Most systems require explicit Big Five questionnaires. Modelling Emotions in Face-to-Face Settings showed personality-aware fusion, but we need cold-start personality inference from signals.
- *MMLLM Fusion of Physiological Signals and Dialogue: Encoding Physiology into LLM Space*  
  LLMs excel in text/dialogue but cannot handle physiological signals directly. Inspired by AFFEC’s scenario prompts, this project encodes physiology as tokens for hybrid modelling.
- *MMLLM Fusion of Physiological Signals and Dialogue: Next-Event Prediction Tasks*  
  Like LLMs predict next words, multimodal affective systems could predict next physiological events. This project develops pretraining tasks for multimodal physiological MMLLMs.
- *Personality Prediction from Physiological Signals: Multimodal Personality Prediction*  
  Physiological signals correlate with personality traits, as shown in Modelling Emotions in Face-to-Face Settings. This project systematically compares modalities for predicting Big Five.
- *Personality Prediction from Physiological Signals: Dynamic Personality Prediction*  
  Traits are not fully static. Exploring Temporal Dynamics of Facial Mimicry showed context-dependent variation. This project explores time-varying personality embeddings.
- *Felt vs. Perceived Emotion: Physiological vs. Self-Annotation*  
  AFFEC provides both felt (E_f) and perceived (E_p) labels. Prior work showed divergence between internal and external states. This project quantifies physiological alignment with both.
- *Cognitive Load from Physiological Signals: Multimodal Cognitive Load Prediction*  
  Cognitive load is a central factor in learning, decision-making, and human–AI interaction. Physiological signals such as pupillometry, EEG band power ratios (e.g., theta/beta), and galvanic skin response (GSR) have long been used as indicators of mental workload. This project explores how these signals can be combined to build predictive models of cognitive load.

## Test theories of neuroscience & cognitive psychology for information processing

- Multiple timescales in perception & action
- Hierarchical & statistical learning

## Computational model of the uncanny valley effect using machine learning
The uncanny valley (UV) is a negative emotional reaction to artificial characters that look almost, but not quite, human. We have collected EEG data from 30 subjects on this topic, and we need a thorough analysis of the data using standard EEG analysis tools to better understand how this phenomenon works.

## Small Language Models in Games

- *Judging quality with SLMs: How good can we get?*  
  A common procedure for benchmarking language model outputs is called LLM-as-a-judge. Small language models (SLMs), say around 1 billion parameters, can be a promising technology for some offline use cases, such as dynamic game content generation, because they can run locally on user devices. In such a case, it is necessary to avoid exposing the user to bad outputs; LLMs cannot be used for judging in this case. Is it possible, for a specific use case, to train an SLM that can reliably identify the bad generations?
- *Design your own SLM-based game!*  
  As a means to create new video game experiences, there has been a lot of interest in “open” or “dynamic” gameplay experiences. “No Man’s Sky” is both an excellent example of the type of interest a game with such an emphasis can generate among gamers, but also of how difficult it is to achieve. Recent advances in large language models suggest an avenue to achieve this, but leveraging these has many issues, among others, of needing to be online. By breaking down tasks into smaller components, small language models become a viable alternative. Can you come up with a game loop which features dynamic content creation that is well enough scoped for a small language model to handle it? How would you measure it? -->

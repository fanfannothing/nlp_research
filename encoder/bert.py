#-*- coding:utf-8 -*-
import tensorflow as tf
from language_model.bert import modeling
from language_model.bert import optimization
from language_model.bert import tokenization
from encoder import EncoderBase
import pdb
import copy

class Bert(EncoderBase):
    def __init__(self, **kwargs):
        """
        :param config:
        """
        super(Bert, self).__init__(**kwargs)
        self.embedding_dim = kwargs['embedding_size']
        self.is_training = kwargs['is_training']
        self.bert_config_file = kwargs['bert_config_file_path']
        self.bert_config = modeling.BertConfig.from_json_file(self.bert_config_file)
        self.vocab_file = kwargs['vocab_file_path']
        self.bert_out_layer = kwargs['bert_out_layer'] if 'bert_out_layer' in kwargs else -1
        self.placeholder = {}

    def __call__(self, name = 'encoder', features = None, reuse = tf.AUTO_REUSE, **kwargs):
        self.placeholder[name+'_input_ids'] = tf.placeholder(tf.int32, 
                                        shape=[None, self.maxlen], 
                                        name = name+"_input_ids")
        self.placeholder[name+'_input_mask'] = tf.placeholder(tf.int32, 
                                        shape=[None, self.maxlen], 
                                        name = name+"_input_mask")
        self.placeholder[name+'_segment_ids'] = tf.placeholder(tf.int32, 
                                        shape=[None, self.maxlen], 
                                        name = name+"_segment_ids")
        if features != None:
            self.placeholder[name+'_input_ids'] = features[name+'_input_ids']
            self.placeholder[name+'_input_mask'] = features[name+'_input_mask']
            self.placeholder[name+'_segment_ids'] = features[name+'_segment_ids']

        #with tf.variable_scope("bert", reuse = reuse):
        #bert_out_layer: 1-12,or -1 represent last layer of bert

        model = modeling.BertModel(
            config=self.bert_config,
            is_training=self.is_training,#True,
            input_ids=self.placeholder[name+"_input_ids"],
            input_mask=self.placeholder[name+'_input_mask'],
            token_type_ids=self.placeholder[name+'_segment_ids'],
            use_one_hot_embeddings=False,
            bert_out_layer = self.bert_out_layer)


        output_layer = model.get_pooled_output()

        hidden_size = output_layer.shape[-1].value

        output_weights = tf.get_variable(
            "output_weights", [self.num_output, hidden_size],
            initializer=tf.truncated_normal_initializer(stddev=0.02))
        output_bias = tf.get_variable(
            "output_bias", [self.num_output], initializer=tf.zeros_initializer())

        with tf.variable_scope("dense"):
            #output_layer = tf.nn.dropout(output_layer, keep_prob=self.keep_prob)
            logits = tf.matmul(output_layer, output_weights, transpose_b=True)
            logits = tf.nn.bias_add(logits, output_bias)
            return logits

    def _truncate_seq_pair(self, tokens_a, tokens_b, max_length):
        """Truncates a sequence pair in place to the maximum length."""
        # This is a simple heuristic which will always truncate the longer sequence
        # one token at a time. This makes more sense than truncating an equal percent
        # of tokens from each, since if one sequence is very short then each token
        # that's truncated likely contains more information than a longer sequence.
        while True:
            total_length = len(tokens_a) + len(tokens_b)
            if total_length <= max_length:
                break
            if len(tokens_a) > len(tokens_b):
                tokens_a.pop()
            else:
                tokens_b.pop()

    def build_ids(self, text_a, text_b = None, **kwargs):
        tokenizer = tokenization.FullTokenizer(vocab_file=self.vocab_file, 
                                               do_lower_case=True)

        tokens_a = tokenizer.tokenize(text_a)
        tokens_b = None
        if text_b:
          tokens_b = tokenizer.tokenize(text_b)
        if tokens_b:
          # Modifies `tokens_a` and `tokens_b` in place so that the total
          # length is less than the specified length.
          # Account for [CLS], [SEP], [SEP] with "- 3"
          self._truncate_seq_pair(tokens_a, tokens_b, self.maxlen - 3)
        else:
          # Account for [CLS] and [SEP] with "- 2"
          if len(tokens_a) > self.maxlen - 2:
            tokens_a = tokens_a[0:(self.maxlen - 2)]


        tokens = []
        segment_ids = []
        tokens.append("[CLS]")
        segment_ids.append(0)
        for token in tokens_a:
            tokens.append(token)
            segment_ids.append(0)
        tokens.append("[SEP]")
        segment_ids.append(0)

        if tokens_b:
            for token in tokens_b:
                tokens.append(token)
                segment_ids.append(1)
            tokens.append("[SEP]")
            segment_ids.append(1)

        input_ids = tokenizer.convert_tokens_to_ids(tokens)

        # The mask has 1 for real tokens and 0 for padding tokens. Only real
        # tokens are attended to.
        input_mask = [1] * len(input_ids)

        # Zero-pad up to the sequence length.
        while len(input_ids) < self.maxlen:
            input_ids.append(0)
            input_mask.append(0)
            segment_ids.append(0)

        assert len(input_ids) == self.maxlen
        assert len(input_mask) == self.maxlen
        assert len(segment_ids) == self.maxlen
        return input_ids, input_mask, segment_ids

    def encoder_fun(self, x_query_raw, x_sample_raw = None, name = 'encoder', **kwargs):
        flag = True
        if type(x_query_raw) != list:
            flag = False
            x_query_raw = [x_query_raw]
            if x_sample_raw != None:
                x_sample_raw = [x_sample_raw]

        input_ids, input_mask, segment_ids = [],[],[]
        pdb.set_trace()
        for idx, item in enumerate(x_query_raw):
            if x_sample_raw != None:
                x_sample_raw_item = x_sample_raw[idx]
            else:
                x_sample_raw_item = None
            tmp_input_ids, tmp_input_mask, tmp_segment_ids = \
                self.build_ids(x_query_raw[idx], x_sample_raw_item)
            input_ids.append(tmp_input_ids)
            input_mask.append(tmp_input_mask)
            segment_ids.append(tmp_segment_ids)
        if flag == False:
            input_ids = input_ids[0]
            input_mask = input_mask[0]
            segment_ids = segment_ids[0]
        return {name+"_input_ids": input_ids, 
                name+"_input_mask": input_mask, 
                name+"_segment_ids": segment_ids}

    def keys_to_features(self, name = 'encoder'):
        keys_to_features = {
            name+"_input_ids": tf.FixedLenFeature([self.maxlen], tf.int64), 
            name+"_input_mask": tf.FixedLenFeature([self.maxlen], tf.int64), 
            name+"_segment_ids": tf.FixedLenFeature([self.maxlen], tf.int64)
        }
        return keys_to_features

    def parsed_to_features(self, parsed, name = 'encoder'):
        ret = {
            name + "_input_ids": tf.reshape(parsed[name+ "_input_ids"], [self.maxlen]), 
            name + "_input_mask": tf.reshape(parsed[name + "_input_mask"], [self.maxlen]),
            name+"_segment_ids": tf.reshape(parsed[name + "_segment_ids"], [self.maxlen])
        }
        return ret

    def get_features(self, name = 'encoder'):
        features = {}
        features[name+'_input_ids'] = tf.placeholder(tf.int32, 
                                        shape=[None, self.maxlen], 
                                        name = name+"_input_ids")
        features[name+'_input_mask'] = tf.placeholder(tf.int32, 
                                        shape=[None, self.maxlen], 
                                        name = name+"_input_mask")
        features[name+'_segment_ids'] = tf.placeholder(tf.int32, 
                                        shape=[None, self.maxlen], 
                                        name = name+"_segment_ids")
        return features
